import handler from '../[...route].js';

export default function authLoginRoute(req, res) {
  req.query = { ...(req.query || {}), route: 'auth/login' };
  return handler(req, res);
}
