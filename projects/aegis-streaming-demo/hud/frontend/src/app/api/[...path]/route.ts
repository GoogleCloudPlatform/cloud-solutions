/**
 * Copyright 2026 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

/* eslint-disable n/no-unsupported-features/node-builtins */
import {NextRequest, NextResponse} from 'next/server';

let cachedIdToken: string | null = null;
let tokenExpiryTimestamp: number = 0;
let inFlightTokenPromise: Promise<string | null> | null = null;

async function getGcpIdToken(audience: string): Promise<string | null> {
  const now = Date.now();
  if (cachedIdToken && now < tokenExpiryTimestamp) {
    return cachedIdToken;
  }
  if (inFlightTokenPromise) {
    return inFlightTokenPromise;
  }

  inFlightTokenPromise = (async () => {
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 3000);
      const metadataUrl =
        'http://metadata.google.internal/computeMetadata/v1/' +
        `instance/service-accounts/default/identity?audience=${encodeURIComponent(
          audience
        )}`;
      const res = await fetch(metadataUrl, {
        headers: {'Metadata-Flavor': 'Google'},
        signal: controller.signal,
      });
      clearTimeout(timer);
      if (res.ok) {
        const token = (await res.text()).trim();
        cachedIdToken = token;
        tokenExpiryTimestamp = Date.now() + 50 * 60 * 1000;
        console.log(
          '[Proxy] Metadata Server ID Token refreshed & cached for audience ' +
            `${audience} (len: ${token.length})`
        );
        return token;
      }
    } catch (err) {
      console.debug('[Proxy] Metadata Server fetch skipped/errored:', err);
    } finally {
      inFlightTokenPromise = null;
    }
    return cachedIdToken;
  })();

  return inFlightTokenPromise;
}

export async function GET(
  request: NextRequest,
  context: {params: Promise<{path?: string[]}>}
) {
  return proxyRequest(request, context);
}

export async function POST(
  request: NextRequest,
  context: {params: Promise<{path?: string[]}>}
) {
  return proxyRequest(request, context);
}

export async function PUT(
  request: NextRequest,
  context: {params: Promise<{path?: string[]}>}
) {
  return proxyRequest(request, context);
}

export async function DELETE(
  request: NextRequest,
  context: {params: Promise<{path?: string[]}>}
) {
  return proxyRequest(request, context);
}

async function proxyRequest(
  request: NextRequest,
  context: {params: Promise<{path?: string[]}>}
) {
  const backendUrl = (
    process.env.BACKEND_API_URL ||
    process.env.NEXT_PUBLIC_HUD_BACKEND_URL ||
    'https://hud-backend-yww5w7x2xa-uc.a.run.app'
  ).replace(/\/$/, '');

  const resolvedParams = await context.params;
  const pathSegments = resolvedParams?.path || [];
  const path = pathSegments.join('/');
  const searchParams = request.nextUrl.search;
  const targetUrl = `${backendUrl}/api/${path}${searchParams}`;

  const reqHeaders = new Headers();
  if (request.headers.get('accept')) {
    reqHeaders.set('accept', request.headers.get('accept')!);
  }
  if (request.headers.get('content-type')) {
    reqHeaders.set('content-type', request.headers.get('content-type')!);
  }

  // Replace incoming frontend auth token with backend ID token from metadata server
  const backendToken = await getGcpIdToken(backendUrl);
  if (backendToken) {
    reqHeaders.set('Authorization', `Bearer ${backendToken}`);
  }

  const body = ['GET', 'HEAD'].includes(request.method)
    ? undefined
    : await request.blob();
  const isSse =
    path.includes('stream') ||
    request.headers.get('accept')?.includes('text/event-stream');

  try {
    const controller = new AbortController();
    const timer = isSse ? null : setTimeout(() => controller.abort(), 45000);

    const response = await fetch(targetUrl, {
      method: request.method,
      headers: reqHeaders,
      body,
      signal: isSse ? undefined : controller.signal,
    });
    if (timer) clearTimeout(timer);

    console.log(
      `[Proxy] Target ${targetUrl} responded with status ` +
        `${response.status} ${response.statusText}`
    );

    const isResponseSse =
      isSse ||
      response.headers.get('content-type')?.includes('text/event-stream');
    if (isResponseSse) {
      return new NextResponse(response.body, {
        status: response.status,
        statusText: response.statusText,
        headers: {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache, no-transform',
          Connection: 'keep-alive',
        },
      });
    }

    const data = await response.arrayBuffer();
    const resHeaders = new Headers(response.headers);

    return new NextResponse(data, {
      status: response.status,
      statusText: response.statusText,
      headers: resHeaders,
    });
  } catch (err: unknown) {
    console.error('Error proxying request to backend:', err);
    return NextResponse.json(
      {error: 'Backend proxy error', details: String(err)},
      {status: 500}
    );
  }
}
