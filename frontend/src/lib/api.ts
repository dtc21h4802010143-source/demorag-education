import axios from 'axios';

export const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000';

export const api = axios.create({
  baseURL: API_BASE,
});

export function getAdminToken() {
  return localStorage.getItem('admin_token') || '';
}

export function setAdminToken(token: string) {
  localStorage.setItem('admin_token', token);
}

export function getUserToken() {
  return localStorage.getItem('user_token') || '';
}

export function setUserToken(token: string) {
  localStorage.setItem('user_token', token);
}

export function clearUserToken() {
  localStorage.removeItem('user_token');
}

export function getClientId() {
  const existing = localStorage.getItem('anon_client_id');
  if (existing) return existing;

  const next = `anon-${Math.random().toString(36).slice(2)}-${Date.now()}`;
  localStorage.setItem('anon_client_id', next);
  return next;
}
