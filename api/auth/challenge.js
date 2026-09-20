import handler from '../[...route].js';

export default function authChallengeRoute(req, res) {
  req.query = { ...(req.query || {}), route: 'auth/challenge' };
  return handler(req, res);
}
