import crypto from 'node:crypto';
import bcrypt from 'bcryptjs';
import { MongoClient } from 'mongodb';

const g=globalThis;
const DB_NAME=()=>process.env.MONGODB_DB||'mh_analysis_license';
const TZ=()=>process.env.LICENSE_TIMEZONE||'Asia/Karachi';
function out(res,s,p){res.statusCode=s;res.setHeader('Content-Type','application/json; charset=utf-8');res.setHeader('Cache-Control','no-store');res.end(JSON.stringify(p));}
function uname(v){return String(v||'').trim().toLowerCase();}
function hash(v){return crypto.createHash('sha256').update(String(v??'')).digest('hex');}
function addr(req){const x=req.headers['x-forwarded-for'];return typeof x==='string'&&x?x.split(',')[0].trim():'';}
function today(){const p=new Intl.DateTimeFormat('en-GB',{timeZone:TZ(),year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date());const m=Object.fromEntries(p.map(x=>[x.type,x.value]));return `${m.year}-${m.month}-${m.day}`;}
async function db(){if(!g.__mhLoginMongo){const c=new MongoClient(process.env.MONGODB_URI,{maxPoolSize:10,serverSelectionTimeoutMS:7000});g.__mhLoginMongo=c.connect().catch(e=>{g.__mhLoginMongo=null;throw e;});}return(await g.__mhLoginMongo).db(DB_NAME());}
async function log(d,u,type,ip,deviceId,detail={}){try{await d.collection('activity').insertOne({username:uname(u),type,ipHash:ip?hash(ip):'',deviceId:String(deviceId||'').slice(0,180),detail,createdAt:new Date()});}catch(e){console.error('AUTH_ACTIVITY_ERROR',e?.message||e);}}
function parseKey(v){const s=String(v||'').trim();if(!s)throw new Error('empty_key');if(s.includes('BEGIN PUBLIC KEY'))return crypto.createPublicKey(s);const b=Buffer.from(s.replace(/\s+/g,''),'base64');if(!b.length)throw new Error('empty_decoded_key');try{return crypto.createPublicKey({key:b,format:'der',type:'spki'});}catch(e){if(b.length===32){const prefix=Buffer.from('302a300506032b6570032100','hex');return crypto.createPublicKey({key:Buffer.concat([prefix,b]),format:'der',type:'spki'});}throw new Error(`unsupported_key_${b.length}`);}}
function fp(key){return crypto.createHash('sha256').update(key.export({type:'spki',format:'der'})).digest('hex');}
function signToken(payload,ttl,aud){const now=Math.floor(Date.now()/1000),h=Buffer.from(JSON.stringify({alg:'HS256',typ:'JWT'})).toString('base64url'),b=Buffer.from(JSON.stringify({...payload,aud,iat:now,exp:now+ttl})).toString('base64url'),u=`${h}.${b}`,s=crypto.createHmac('sha256',process.env.JWT_SECRET).update(u).digest('base64url');return `${u}.${s}`;}

export default async function handler(req,res){
 if(req.method!=='POST')return out(res,405,{ok:false,error:'METHOD_NOT_ALLOWED'});
 try{
  if(!process.env.MONGODB_URI||!process.env.JWT_SECRET)return out(res,500,{ok:false,error:'SERVER_NOT_CONFIGURED'});
  const b=req.body&&typeof req.body==='object'?req.body:{},u=uname(b.username),pw=String(b.password||''),cid=String(b.challenge_id||''),sig=String(b.signature||''),pub=String(b.public_key||''),deviceId=String(b.device_id||'').trim().slice(0,180),info=b.device_info&&typeof b.device_info==='object'?b.device_info:{},ip=addr(req),d=await db(),users=d.collection('users'),user=await users.findOne({username:u});
  if(!user||!await bcrypt.compare(pw,user.passwordHash)){console.warn('AUTH_REJECT credentials',{username:u});await log(d,u,'LOGIN_FAILED',ip,deviceId,{reason:'credentials'});return out(res,401,{ok:false,error:'INVALID_CREDENTIALS'});}
  const t=today();if(user.status!=='active'||(user.validFrom&&t<user.validFrom)||(user.validUntil&&t>user.validUntil)){const code=user.status!=='active'?'ACCOUNT_DISABLED':(user.validFrom&&t<user.validFrom?'LICENSE_NOT_STARTED':'LICENSE_EXPIRED');await log(d,u,code,ip,deviceId);return out(res,403,{ok:false,error:code});}
  const ch=await d.collection('challenges').findOne({_id:cid});if(!ch||ch.used||ch.expiresAt<=new Date()||ch.usernameHash!==hash(u)||ch.deviceIdHash!==hash(deviceId)){console.warn('AUTH_REJECT challenge',{username:u});await log(d,u,'LOGIN_FAILED',ip,deviceId,{reason:'challenge'});return out(res,401,{ok:false,error:'INVALID_CHALLENGE'});}
  let key,fingerprint;try{key=parseKey(pub);fingerprint=fp(key);}catch(e){console.warn('AUTH_REJECT device_key',{username:u,reason:e.message,keyLength:pub.length});await log(d,u,'LOGIN_FAILED',ip,deviceId,{reason:'device_key',diagnostic:String(e.message).slice(0,80)});return out(res,401,{ok:false,error:'INVALID_DEVICE_KEY'});}
  const signature=Buffer.from(sig.replace(/\s+/g,''),'base64');if(!signature.length||!crypto.verify(null,Buffer.from(ch.challenge,'utf8'),key,signature)){console.warn('AUTH_REJECT device_signature',{username:u,signatureLength:signature.length});await log(d,u,'LOGIN_FAILED',ip,deviceId,{reason:'device_signature'});return out(res,401,{ok:false,error:'INVALID_DEVICE_SIGNATURE'});}
  const consumed=await d.collection('challenges').updateOne({_id:cid,used:false},{$set:{used:true}});if(consumed.modifiedCount!==1){await log(d,u,'LOGIN_FAILED',ip,deviceId,{reason:'challenge_race'});return out(res,401,{ok:false,error:'INVALID_CHALLENGE'});}
  const machineIdHash=hash(deviceId),storedMachineIdHash=user.device?.machineIdHash||'';
  if(storedMachineIdHash&&storedMachineIdHash!==machineIdHash){await log(d,u,'UNAUTHORIZED_DEVICE',ip,deviceId,{reason:'machine_mismatch'});return out(res,403,{ok:false,error:'DEVICE_NOT_AUTHORIZED',message:'This account is already activated on another device. Contact administrator.'});}
  if(!storedMachineIdHash&&user.device?.publicKeyFingerprint&&user.device.publicKeyFingerprint!==fingerprint){await log(d,u,'UNAUTHORIZED_DEVICE',ip,deviceId,{reason:'legacy_key_mismatch'});return out(res,403,{ok:false,error:'DEVICE_NOT_AUTHORIZED',message:'This account is already activated on another device. Contact administrator.'});}
  const now=new Date(),first=!user.device?.publicKeyFingerprint,clean={device_name:String(info.device_name||info.machine_name||'').slice(0,120),os_version:String(info.os_version||info.os||'').slice(0,120),arch:String(info.arch||'').slice(0,40),app_version:String(info.app_version||'').slice(0,40)};
  const device=first?{deviceId,machineIdHash,publicKeyFingerprint:fingerprint,publicKey:pub,info:clean,boundAt:now,lastSeenAt:now,firstIpHash:hash(ip),lastIpHash:hash(ip)}:{...user.device,deviceId,machineIdHash,publicKeyFingerprint:fingerprint,publicKey:pub,info:{...user.device.info,...clean},lastSeenAt:now,lastIpHash:hash(ip)};
  await users.updateOne({_id:user._id},{$set:{device,lastLoginAt:now,updatedAt:now}});await log(d,u,first?'DEVICE_BOUND':'LOGIN_SUCCESS',ip,deviceId,{machineBound:true});console.info('AUTH_SUCCESS',{username:u,firstDevice:first});const tv=user.tokenVersion||1;return out(res,200,{ok:true,access_token:signToken({sub:String(user._id),username:u,dfp:fingerprint,tv},1800,'mh-analysis'),expires_in:1800,username:u,valid_from:user.validFrom,valid_until:user.validUntil,device_bound:true,max_devices:1,user:{username:u,valid_from:user.validFrom,valid_until:user.validUntil,device_id:deviceId}});
 }catch(e){console.error('AUTH_LOGIN_SERVER_ERROR',e);return out(res,500,{ok:false,error:'SERVER_ERROR'});}
}
