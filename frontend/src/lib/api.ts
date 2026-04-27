export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers || {})
    },
    cache: "no-store"
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<T>;
}

export type Campaign = {
  id: string;
  name: string;
  description: string;
  mode: string;
  current_scene: Record<string, unknown>;
};

export type Overview = {
  characters: Array<Record<string, any>>;
  npcs: Array<Record<string, any>>;
  quests: Array<Record<string, any>>;
};

