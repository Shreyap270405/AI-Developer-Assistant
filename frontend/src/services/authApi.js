import api from './api';

/** Authenticate a user and return { message, user }. */
export async function login(email, password) {
  const { data } = await api.post('/auth/login', { email, password });
  return data;
}

/** Register a new user and return { message, user }. */
export async function register(email, password, fullName) {
  const { data } = await api.post('/auth/register', {
    email,
    password,
    full_name: fullName,
  });
  return data;
}

/** Fetch the currently authenticated user's profile. */
export async function fetchMe() {
  const { data } = await api.get('/auth/me');
  return data;
}

/** Logout the user by clearing HttpOnly cookies. */
export async function logout() {
  const { data } = await api.post('/auth/logout');
  return data;
}
