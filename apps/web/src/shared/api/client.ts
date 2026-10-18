const API_URL = import.meta.env.VITE_API_URL ?? "";

interface ProblemResponse {
  title?: string;
  detail?: string;
  fieldErrors?: Record<string, string>;
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly problem: ProblemResponse,
  ) {
    super(
      problem.detail ?? problem.title ?? `Request failed with status ${status}`,
    );
  }
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
  token?: string,
): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });

  if (response.status === 401 && token) {
    window.dispatchEvent(new CustomEvent("sems:unauthorized", { detail: token }));
  }
  if (!response.ok) {
    let problem: ProblemResponse = {};
    try {
      problem = (await response.json()) as ProblemResponse;
    } catch {
      problem = { detail: response.statusText };
    }
    throw new ApiError(response.status, problem);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}
