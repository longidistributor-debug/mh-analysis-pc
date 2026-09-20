import handler from '../[...route].js';

export default function adminUserActionRoute(req, res) {
  req.query = { ...(req.query || {}), route: 'admin/user-action' };
  return handler(req, res);
}
