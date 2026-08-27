import type { FetchLike } from "../../apps/server/clients/http.js";

export interface RecordedRequest {
  readonly method: string;
  readonly url: URL;
  readonly headers: Headers;
  readonly body: string | undefined;
}

export type Responder = (request: RecordedRequest) => Response;

interface Route {
  readonly method: string;
  readonly pathname: string;
  readonly respond: Responder;
}

export class FakeFetch {
  readonly calls: RecordedRequest[] = [];
  private readonly routes: Route[] = [];

  on(method: string, pathname: string, respond: Responder | Response): this {
    this.routes.unshift({
      method,
      pathname,
      respond: typeof respond === "function" ? respond : () => respond.clone(),
    });
    return this;
  }

  onJson(
    method: string,
    pathname: string,
    body: unknown,
    init: ResponseInit = {},
  ): this {
    return this.on(
      method,
      pathname,
      () =>
        new Response(JSON.stringify(body), {
          status: 200,
          ...init,
          headers: { "content-type": "application/json", ...init.headers },
        }),
    );
  }

  callsTo(method: string, pathname: string): RecordedRequest[] {
    return this.calls.filter(
      (call) => call.method === method && call.url.pathname === pathname,
    );
  }

  get lastCall(): RecordedRequest {
    const call = this.calls.at(-1);
    if (call === undefined) {
      throw new Error("no request was made");
    }
    return call;
  }

  readonly fetch: FetchLike = async (url, init) => {
    const method = (init?.method ?? "GET").toUpperCase();
    const parsed = new URL(url);
    const request: RecordedRequest = {
      method,
      url: parsed,
      headers: new Headers(init?.headers),
      body: typeof init?.body === "string" ? init.body : undefined,
    };
    this.calls.push(request);

    const route = this.routes.find(
      (candidate) =>
        candidate.method === method && candidate.pathname === parsed.pathname,
    );
    if (route === undefined) {
      throw new Error(`unexpected request: ${method} ${parsed.pathname}`);
    }
    return route.respond(request);
  };
}
