import handler from '../[...route].js';

export default function adminActivityRoute(req, res) {
  req.query = { ...(req.query || {}), route: 'admin/activity' };
  return handler(req, res);
}
