import handler from '../[...route].js';

export default function adminUsersRoute(req, res) {
  req.query = { ...(req.query || {}), route: 'admin/users' };
  return handler(req, res);
}
