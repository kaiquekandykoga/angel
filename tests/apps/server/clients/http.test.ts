import { describe, expect, it } from "vitest";
import {
  getAll,
  HttpClient,
  HttpStatusError,
} from "../../../../apps/server/clients/http.js";
import { FakeFetch } from "../../../helpers/fetch.js";

const BASE = "https://api.example.com";

describe("HttpClient", () => {
  it("resolves a path against the base url", async () => {
    const fake = new FakeFetch().onJson("GET", "/things", []);

    await new HttpClient(BASE, {}, fake.fetch).get("/things");

    expect(fake.lastCall.url.origin).toBe(BASE);
    expect(fake.lastCall.url.pathname).toBe("/things");
  });

  it("keeps an absolute url as it is", async () => {
    const fake = new FakeFetch().onJson("GET", "/page-two", []);

    await new HttpClient(BASE, {}, fake.fetch).get(`${BASE}/page-two?page=2`);

    expect(fake.lastCall.url.searchParams.get("page")).toBe("2");
  });

  it("sends the default headers and the per-call headers", async () => {
    const fake = new FakeFetch().onJson("GET", "/things", []);

    await new HttpClient(BASE, { "x-api-version": "1" }, fake.fetch).get("/things", {
      headers: { authorization: "Bearer t" },
    });

    expect(fake.lastCall.headers.get("x-api-version")).toBe("1");
    expect(fake.lastCall.headers.get("authorization")).toBe("Bearer t");
  });

  it("serialises query parameters", async () => {
    const fake = new FakeFetch().onJson("GET", "/things", []);

    await new HttpClient(BASE, {}, fake.fetch).get("/things", {
      params: { state: "open", per_page: 100 },
    });

    expect(fake.lastCall.url.searchParams.get("state")).toBe("open");
    expect(fake.lastCall.url.searchParams.get("per_page")).toBe("100");
  });

  it("posts JSON with the matching content type", async () => {
    const fake = new FakeFetch().onJson("POST", "/things", {}, { status: 201 });

    await new HttpClient(BASE, {}, fake.fetch).post("/things", {
      json: { name: "a" },
    });

    expect(fake.lastCall.headers.get("content-type")).toBe("application/json");
    expect(fake.lastCall.body).toBe('{"name":"a"}');
  });

  it("sends no body when there is nothing to post", async () => {
    const fake = new FakeFetch().onJson("POST", "/things", {}, { status: 201 });

    await new HttpClient(BASE, {}, fake.fetch).post("/things");

    expect(fake.lastCall.body).toBeUndefined();
  });
});

describe("HttpResponse", () => {
  it("names the status, method and url when it raises", async () => {
    const fake = new FakeFetch().on(
      "GET",
      "/things",
      new Response("no", { status: 404 }),
    );

    const response = await new HttpClient(BASE, {}, fake.fetch).get("/things");

    expect(() => response.ensureOk()).toThrow(HttpStatusError);
    expect(() => response.ensureOk()).toThrow(`404 response from GET ${BASE}/things`);
  });

  it("returns itself for a 2xx status", async () => {
    const fake = new FakeFetch().onJson("GET", "/things", []);

    const response = await new HttpClient(BASE, {}, fake.fetch).get("/things");

    expect(response.ensureOk()).toBe(response);
  });

  it("finds the next url in a Link header", async () => {
    const fake = new FakeFetch().onJson("GET", "/things", [], {
      headers: {
        link: `<${BASE}/things?page=3>; rel="last", <${BASE}/things?page=2>; rel="next"`,
      },
    });

    const response = await new HttpClient(BASE, {}, fake.fetch).get("/things");

    expect(response.nextUrl()).toBe(`${BASE}/things?page=2`);
  });

  it("has no next url when the Link header has no next", async () => {
    const fake = new FakeFetch().onJson("GET", "/things", [], {
      headers: { link: `<${BASE}/things?page=1>; rel="prev"` },
    });

    const response = await new HttpClient(BASE, {}, fake.fetch).get("/things");

    expect(response.nextUrl()).toBeUndefined();
  });

  it("has no next url without a Link header", async () => {
    const fake = new FakeFetch().onJson("GET", "/things", []);

    const response = await new HttpClient(BASE, {}, fake.fetch).get("/things");

    expect(response.nextUrl()).toBeUndefined();
  });
});

describe("getAll", () => {
  it("returns a single page as it is", async () => {
    const fake = new FakeFetch().onJson("GET", "/things", [1, 2]);

    await expect(
      getAll<number>(new HttpClient(BASE, {}, fake.fetch), "/things"),
    ).resolves.toEqual([1, 2]);
  });

  it("follows every next link and drops the original parameters", async () => {
    const fake = new FakeFetch().on("GET", "/things", (request) =>
      request.url.searchParams.get("page") === "2"
        ? Response.json([3])
        : Response.json([1, 2], {
            headers: { link: `<${BASE}/things?page=2>; rel="next"` },
          }),
    );

    await expect(
      getAll<number>(new HttpClient(BASE, {}, fake.fetch), "/things", {
        params: { per_page: 100 },
      }),
    ).resolves.toEqual([1, 2, 3]);
    expect(fake.calls[0]?.url.searchParams.get("per_page")).toBe("100");
    expect(fake.calls[1]?.url.searchParams.get("per_page")).toBeNull();
  });

  it("reads the items out of a keyed payload", async () => {
    const fake = new FakeFetch().onJson("GET", "/things", { items: [1, 2] });

    await expect(
      getAll<number>(new HttpClient(BASE, {}, fake.fetch), "/things", {
        key: "items",
      }),
    ).resolves.toEqual([1, 2]);
  });

  it("treats a missing key as an empty page", async () => {
    const fake = new FakeFetch().onJson("GET", "/things", { total: 0 });

    await expect(
      getAll<number>(new HttpClient(BASE, {}, fake.fetch), "/things", {
        key: "items",
      }),
    ).resolves.toEqual([]);
  });

  it("raises on a non-2xx page", async () => {
    const fake = new FakeFetch().on(
      "GET",
      "/things",
      new Response("no", { status: 500 }),
    );

    await expect(
      getAll(new HttpClient(BASE, {}, fake.fetch), "/things"),
    ).rejects.toThrow(HttpStatusError);
  });
});
