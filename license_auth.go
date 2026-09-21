//go:build windows

package main

import (
 "bytes"
 "crypto/ed25519"
 "crypto/rand"
 "crypto/sha256"
 "crypto/x509"
 "encoding/base64"
 "encoding/hex"
 "encoding/json"
 "errors"
 "fmt"
 "io"
 "net/http"
 "os"
 "path/filepath"
 "runtime"
 "strings"
 "sync"
 "syscall"
 "time"
 "unsafe"

 "golang.org/x/sys/windows/registry"
)

const licDefaultBaseURL = "https://mh-analysis.vercel.app"
var licAppVersion = "DEV"

type licDataBlob struct { cbData uint32; pbData *byte }
var (
 licCrypt32=syscall.NewLazyDLL("crypt32.dll")
 licKernel32=syscall.NewLazyDLL("kernel32.dll")
 licCryptProtectData=licCrypt32.NewProc("CryptProtectData")
 licCryptUnprotectData=licCrypt32.NewProc("CryptUnprotectData")
 licLocalFree=licKernel32.NewProc("LocalFree")
 licMu sync.Mutex
 licSessionMem *licSession
 licAuthorized bool
 licLastCheck time.Time
 licLastCode string
 licLastMessage string
 licHTTP=&http.Client{Timeout:12*time.Second}
 licRemoteCheckMinSpacing=90*time.Second
)
type licDeviceDisk struct{ PrivateKey string `json:"private_key"` }
type licDevice struct{ Private ed25519.PrivateKey; Public ed25519.PublicKey; DER []byte; ID string }
type licUserInfo struct{ Username string `json:"username"`; ValidFrom string `json:"valid_from"`; ValidUntil string `json:"valid_until"`; DeviceID string `json:"device_id"` }
type licSession struct{ Username string `json:"username"`; AccessToken string `json:"access_token"`; User licUserInfo `json:"user"`; SavedAt time.Time `json:"saved_at"` }
type licRemoteEnvelope struct{ OK bool `json:"ok"`; Code string `json:"code"`; Error string `json:"error"`; Message string `json:"message"`; AccessToken string `json:"access_token"`; User licUserInfo `json:"user"`; ChallengeID string `json:"challenge_id"`; Challenge string `json:"challenge"`; ExpiresIn int `json:"expires_in"` }
func licBaseURL()string{if v:=strings.TrimSpace(os.Getenv("MH_AUTH_BASE_URL"));v!=""{return strings.TrimRight(v,"/")};return licDefaultBaseURL}
func licRootDir()string{b:=os.Getenv("LOCALAPPDATA");if b==""{if d,e:=os.UserConfigDir();e==nil{b=d}else{b=os.TempDir()}};return filepath.Join(b,"MHAnalysis")}
func licDevicePath()string{return filepath.Join(licRootDir(),"license-device-v1.bin")}
func licSessionPath()string{return filepath.Join(licRootDir(),"license-session-v1.bin")}
func licBlobFromBytes(b []byte)licDataBlob{if len(b)==0{return licDataBlob{}};return licDataBlob{uint32(len(b)),&b[0]}}
func licBytesFromBlob(b licDataBlob)[]byte{if b.cbData==0||b.pbData==nil{return nil};src:=unsafe.Slice(b.pbData,int(b.cbData));out:=make([]byte,len(src));copy(out,src);return out}
func licDPAPIProtect(data []byte)([]byte,error){if len(data)==0{return nil,errors.New("empty dpapi input")};in:=licBlobFromBytes(data);var out licDataBlob;r,_,e:=licCryptProtectData.Call(uintptr(unsafe.Pointer(&in)),0,0,0,0,1,uintptr(unsafe.Pointer(&out)));if r==0{return nil,fmt.Errorf("CryptProtectData failed: %v",e)};defer licLocalFree.Call(uintptr(unsafe.Pointer(out.pbData)));return licBytesFromBlob(out),nil}
func licDPAPIUnprotect(data []byte)([]byte,error){if len(data)==0{return nil,errors.New("empty dpapi input")};in:=licBlobFromBytes(data);var out licDataBlob;r,_,e:=licCryptUnprotectData.Call(uintptr(unsafe.Pointer(&in)),0,0,0,0,0,1,uintptr(unsafe.Pointer(&out)));if r==0{return nil,fmt.Errorf("CryptUnprotectData failed: %v",e)};defer licLocalFree.Call(uintptr(unsafe.Pointer(out.pbData)));return licBytesFromBlob(out),nil}
func licWriteProtected(path string,v any)error{raw,e:=json.Marshal(v);if e!=nil{return e};enc,e:=licDPAPIProtect(raw);if e!=nil{return e};if e=os.MkdirAll(filepath.Dir(path),0700);e!=nil{return e};tmp:=path+".tmp";if e=os.WriteFile(tmp,enc,0600);e!=nil{return e};_ = os.Remove(path);return os.Rename(tmp,path)}
func licReadProtected(path string,v any)error{enc,e:=os.ReadFile(path);if e!=nil{return e};raw,e:=licDPAPIUnprotect(enc);if e!=nil{return e};return json.Unmarshal(raw,v)}
func licStableMachineID()(string,error){k,e:=registry.OpenKey(registry.LOCAL_MACHINE,`SOFTWARE\Microsoft\Cryptography`,registry.QUERY_VALUE);if e!=nil{return "",fmt.Errorf("open MachineGuid: %w",e)};defer k.Close();guid,_,e:=k.GetStringValue("MachineGuid");if e!=nil||strings.TrimSpace(guid)==""{return "",errors.New("Windows MachineGuid is unavailable")};s:=sha256.Sum256([]byte(strings.ToLower(strings.TrimSpace(guid))));return hex.EncodeToString(s[:]),nil}
func licBuildDevice(priv ed25519.PrivateKey,machineID string)(*licDevice,error){pub:=priv.Public().(ed25519.PublicKey);der,e:=x509.MarshalPKIXPublicKey(pub);if e!=nil{return nil,e};return &licDevice{priv,pub,der,machineID},nil}
func licEnsureDevice()(*licDevice,error){machineID,e:=licStableMachineID();if e!=nil{return nil,e};path:=licDevicePath();var disk licDeviceDisk;if _,se:=os.Stat(path);se==nil{if e=licReadProtected(path,&disk);e==nil{raw,de:=base64.StdEncoding.DecodeString(disk.PrivateKey);if de==nil&&len(raw)==ed25519.PrivateKeySize{return licBuildDevice(ed25519.PrivateKey(raw),machineID)}};/* stale/corrupt local identity is safe to regenerate; server still enforces machine device_id */ _=os.Remove(path)}else if !os.IsNotExist(se){return nil,se};_,priv,e:=ed25519.GenerateKey(rand.Reader);if e!=nil{return nil,e};if e=licWriteProtected(path,licDeviceDisk{base64.StdEncoding.EncodeToString(priv)});e!=nil{return nil,e};return licBuildDevice(priv,machineID)}
func licLoadSession()*licSession{return licSessionMem}
func licSaveSession(s *licSession)error{s.SavedAt=time.Now();licSessionMem=s;_ = os.Remove(licSessionPath());return nil}
func licClearSession(){licSessionMem=nil;licAuthorized=false;licLastCheck=time.Time{};_ = os.Remove(licSessionPath())}
func licPost(path string,body any,bearer string)(int,licRemoteEnvelope,error){var env licRemoteEnvelope;raw,e:=json.Marshal(body);if e!=nil{return 0,env,e};req,e:=http.NewRequest(http.MethodPost,licBaseURL()+"/api/"+strings.TrimLeft(path,"/"),bytes.NewReader(raw));if e!=nil{return 0,env,e};req.Header.Set("Content-Type","application/json");req.Header.Set("User-Agent","MH-Analysis/"+licAppVersion);if bearer!=""{req.Header.Set("Authorization","Bearer "+bearer)};resp,e:=licHTTP.Do(req);if e!=nil{return 0,env,e};defer resp.Body.Close();b,_:=io.ReadAll(io.LimitReader(resp.Body,1<<20));_ = json.Unmarshal(b,&env);if env.Code==""{env.Code=env.Error};return resp.StatusCode,env,nil}
func licMachineInfo()map[string]string{host,_:=os.Hostname();return map[string]string{"machine_name":host,"os":runtime.GOOS,"arch":runtime.GOARCH,"app_version":licAppVersion}}
func licSetRemoteError(status int,env licRemoteEnvelope,e error){licAuthorized=false;licLastCheck=time.Now();if e!=nil{licLastCode="internet_required";licLastMessage="Internet connection is required to verify your MH Analysis license.";return};licLastCode=strings.ToLower(strings.TrimSpace(env.Code));licLastMessage=env.Message;if licLastCode==""{if status==401{licLastCode="authorization_required"}else if status==403{licLastCode="authorization_denied"}else{licLastCode="license_server_error"}};if licLastMessage==""{switch licLastCode{case "license_expired":licLastMessage="Your access has expired. Contact administrator for renewal.";case "unauthorized_device","device_not_authorized":licLastMessage="This account is already activated on another device. Contact administrator.";case "account_disabled":licLastMessage="This account is disabled. Contact administrator.";case "license_not_started":licLastMessage="Your license is not active yet. Contact administrator.";default:licLastMessage="License authorization failed."}}}
func licEnsureAuthorized(force bool)bool{licMu.Lock();defer licMu.Unlock();if licAuthorized&&!force&&time.Since(licLastCheck)<licRemoteCheckMinSpacing{return true};s:=licLoadSession();if s==nil{licAuthorized=false;licLastCode="login_required";licLastMessage="Enter your username and password to activate MH Analysis.";return false};d,e:=licEnsureDevice();if e!=nil{licAuthorized=false;licLastCode="device_key_unavailable";licLastMessage="Authorized device key is unavailable. Contact administrator for device reset.";return false};if s.User.DeviceID!=""&&s.User.DeviceID!=d.ID{licAuthorized=false;licLastCode="device_not_authorized";licLastMessage="This installation does not match the authorized device. Contact administrator.";return false};status,vr,ce:=licPost("auth/verify",map[string]any{},s.AccessToken);if ce==nil&&status>=200&&status<300&&vr.OK{s.User=vr.User;_ = licSaveSession(s);licAuthorized=true;licLastCheck=time.Now();licLastCode="";licLastMessage="";return true};licSetRemoteError(status,vr,ce);if status==401{licClearSession();licLastCode="session_invalid";licLastMessage="Your secure session has ended. Please log in again."};return false}
func licHandleLogin(w http.ResponseWriter,r *http.Request){w.Header().Set("Content-Type","application/json");w.Header().Set("Cache-Control","no-store");if r.Method!=http.MethodPost{http.Error(w,"method",405);return};var q struct{Username string `json:"username"`;Password string `json:"password"`};if json.NewDecoder(io.LimitReader(r.Body,64<<10)).Decode(&q)!=nil{http.Error(w,"bad json",400);return};q.Username=strings.ToLower(strings.TrimSpace(q.Username));if q.Username==""||q.Password==""{w.WriteHeader(400);_ = json.NewEncoder(w).Encode(map[string]any{"ok":false,"code":"invalid_request"});return};d,e:=licEnsureDevice();if e!=nil{w.WriteHeader(500);_ = json.NewEncoder(w).Encode(map[string]any{"ok":false,"code":"device_key_failed","message":"Could not create secure device identity: "+e.Error()});return};status,ch,ce:=licPost("auth/challenge",map[string]any{"username":q.Username,"device_id":d.ID},"");if ce!=nil{w.WriteHeader(503);_ = json.NewEncoder(w).Encode(map[string]any{"ok":false,"code":"internet_required","message":"Internet connection is required to log in."});return};if status<200||status>=300||!ch.OK||ch.ChallengeID==""||ch.Challenge==""{if status<400{status=401};w.WriteHeader(status);_ = json.NewEncoder(w).Encode(ch);return};challenge,de:=base64.StdEncoding.DecodeString(ch.Challenge);if de!=nil{w.WriteHeader(502);_ = json.NewEncoder(w).Encode(map[string]any{"ok":false,"code":"bad_challenge"});return};sig:=ed25519.Sign(d.Private,challenge);status,out,ce:=licPost("auth/login",map[string]any{"username":q.Username,"password":q.Password,"device_id":d.ID,"device_public_key":base64.StdEncoding.EncodeToString(d.DER),"challenge_id":ch.ChallengeID,"challenge_signature":base64.StdEncoding.EncodeToString(sig),"machine":licMachineInfo()},"");if ce!=nil{w.WriteHeader(503);_ = json.NewEncoder(w).Encode(map[string]any{"ok":false,"code":"internet_required","message":"Internet connection is required to log in."});return};if status<200||status>=300||!out.OK||out.AccessToken==""{if status<400{status=401};w.WriteHeader(status);_ = json.NewEncoder(w).Encode(out);return};s:=&licSession{Username:q.Username,AccessToken:out.AccessToken,User:out.User};if e=licSaveSession(s);e!=nil{w.WriteHeader(500);_ = json.NewEncoder(w).Encode(map[string]any{"ok":false,"code":"session_save_failed"});return};licMu.Lock();licAuthorized=true;licLastCheck=time.Now();licLastCode="";licLastMessage="";licMu.Unlock();_ = json.NewEncoder(w).Encode(map[string]any{"ok":true,"user":out.User})}
func licHandleLogout(w http.ResponseWriter,r *http.Request){if r.Method!=http.MethodPost{http.Error(w,"method",405);return};licMu.Lock();licClearSession();licMu.Unlock();w.Header().Set("Content-Type","application/json");_ = json.NewEncoder(w).Encode(map[string]any{"ok":true})}
func licHandleStatus(w http.ResponseWriter,r *http.Request){if r.Method!=http.MethodGet{http.Error(w,"method",405);return};ok:=licEnsureAuthorized(false);licMu.Lock();defer licMu.Unlock();w.Header().Set("Content-Type","application/json");w.Header().Set("Cache-Control","no-store");_ = json.NewEncoder(w).Encode(map[string]any{"ok":ok,"code":licLastCode,"message":licLastMessage})}
