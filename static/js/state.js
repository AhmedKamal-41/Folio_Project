export const state = {
  users: [],
  documents: [],
  current: null,
  userId: 1,
  filter: "all",
  busy: false
};

export function storedUserId() {
  try { return Number(sessionStorage.getItem("folio-user")) || 1; }
  catch { return 1; }
}

export function rememberUserId(userId) {
  try { sessionStorage.setItem("folio-user", String(userId)); }
  catch { /* Account persistence is optional; document saves still use the API. */ }
}
