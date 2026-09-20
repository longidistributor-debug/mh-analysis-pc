import handler from '../[...route].js';

export default function adminSessionRoute(req, res) {
  req.query = { ...(req.query || {}), route: 'admin/session' };
  return handler(req, res);
}
