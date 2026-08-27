export type FetchLike = (url: string, init?: RequestInit) => Promise<Response>;

export class HttpStatusError extends Error {
  override readonly name = "HttpStatusError";

  constructor(
    readonly status: number,
    readonly method: string,
    readonly url: string,
  ) {
    super(`${status} response from ${method} ${url}`);
  }
}

export interface RequestOptions {
  readonly params?: Readonly<Record<string, string | number>> | undefined;
  readonly headers?: Readonly<Record<string, string>> | undefined;
}

const LINK_PATTERN = /<([^>]+)>\s*;\s*rel="([^"]+)"/g;

export class HttpResponse {
  constructor(
    private readonly response: Response,
    readonly method: string,
    readonly url: string,
  ) {}

  get status(): number {
    return this.response.status;
  }

  get ok(): boolean {
    return this.response.ok;
  }

  ensureOk(): this {
    if (!this.response.ok) {
      throw new HttpStatusError(this.status, this.method, this.url);
    }
    return this;
  }

  async json<T>(): Promise<T> {
    return (await this.response.json()) as T;
  }

  text(): Promise<string> {
    return this.response.text();
  }

  nextUrl(): string | undefined {
    const link = this.response.headers.get("link");
    if (link === null) {
      return undefined;
    }
    for (const [, url, rel] of link.matchAll(LINK_PATTERN)) {
      if (rel === "next") {
        return url;
      }
    }
    return undefined;
  }
}

export class HttpClient {
  constructor(
    readonly baseUrl: string,
    readonly defaultHeaders: Readonly<Record<string, string>> = {},
    private readonly fetchImpl: FetchLike = fetch,
  ) {}

  private resolve(path: string, params: RequestOptions["params"]): string {
    const url = new URL(path, `${this.baseUrl.replace(/\/$/, "")}/`);
    for (const [key, value] of Object.entries(params ?? {})) {
      url.searchParams.set(key, String(value));
    }
    return url.toString();
  }

  private async request(
    method: string,
    path: string,
    options: RequestOptions & { json?: unknown } = {},
  ): Promise<HttpResponse> {
    const url = this.resolve(path, options.params);
    const headers: Record<string, string> = {
      ...this.defaultHeaders,
      ...options.headers,
    };
    const init: RequestInit = { method, headers };
    if (options.json !== undefined) {
      headers["content-type"] = "application/json";
      init.body = JSON.stringify(options.json);
    }
    return new HttpResponse(await this.fetchImpl(url, init), method, url);
  }

  get(path: string, options: RequestOptions = {}): Promise<HttpResponse> {
    return this.request("GET", path, options);
  }

  post(
    path: string,
    options: RequestOptions & { json?: unknown } = {},
  ): Promise<HttpResponse> {
    return this.request("POST", path, options);
  }
}

export interface GetAllOptions extends RequestOptions {
  readonly key?: string | undefined;
}

export async function getAll<T>(
  client: HttpClient,
  path: string,
  options: GetAllOptions = {},
): Promise<T[]> {
  const items: T[] = [];
  let url = path;
  let params = options.params;
  while (true) {
    const response = (
      await client.get(url, { params, headers: options.headers })
    ).ensureOk();
    const payload = await response.json<T[] | Record<string, T[]>>();
    items.push(
      ...(options.key
        ? ((payload as Record<string, T[]>)[options.key] ?? [])
        : (payload as T[])),
    );
    const next = response.nextUrl();
    if (next === undefined) {
      return items;
    }
    url = next;
    params = undefined;
  }
}
