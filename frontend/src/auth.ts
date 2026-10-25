const CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID;
const TOKEN_KEY = "cca-id-token";

function expiryMs(token: string): number {
  const payload = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
  return JSON.parse(atob(payload)).exp * 1000;
}

// Google ID tokens last about an hour; treat anything expiring within a minute as gone.
function isFresh(token: string): boolean {
  try {
    return expiryMs(token) - 60_000 > Date.now();
  } catch {
    return false;
  }
}

export function loadToken(): string | null {
  const token = localStorage.getItem(TOKEN_KEY);
  return token && isFresh(token) ? token : null;
}

export function saveToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

function waitForGoogle(): Promise<GoogleIdApi> {
  return new Promise((resolve) => {
    const check = () => (window.google ? resolve(window.google.accounts.id) : setTimeout(check, 100));
    check();
  });
}

export async function renderSignIn(element: HTMLElement, onToken: (token: string) => void): Promise<void> {
  const id = await waitForGoogle();
  id.initialize({ client_id: CLIENT_ID, callback: ({ credential }) => onToken(credential) });
  id.renderButton(element, { theme: "outline", size: "large", text: "signin_with" });
}
