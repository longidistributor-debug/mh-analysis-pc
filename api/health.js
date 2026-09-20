import handler from './[...route].js';

export default function healthRoute(req, res) {
  req.query = { ...(req.query || {}), route: 'health' };
  return handler(req, res);
}
