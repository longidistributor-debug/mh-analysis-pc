import handler from '../[...route].js';

export default function authVerifyRoute(req, res) {
  req.query = { ...(req.query || {}), route: 'auth/verify' };
  return handler(req, res);
}
