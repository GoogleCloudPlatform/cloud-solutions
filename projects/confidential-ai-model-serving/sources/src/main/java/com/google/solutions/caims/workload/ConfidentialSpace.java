//
// Copyright 2025 Google LLC
//
// Licensed to the Apache Software Foundation (ASF) under one
// or more contributor license agreements.  See the NOTICE file
// distributed with this work for additional information
// regarding copyright ownership.  The ASF licenses this file
// to you under the Apache License, Version 2.0 (the
// "License"); you may not use this file except in compliance
// with the License.  You may obtain a copy of the License at
//
//   http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing,
// software distributed under the License is distributed on an
// "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
// KIND, either express or implied.  See the License for the
// specific language governing permissions and limitations
// under the License.
//

package com.google.solutions.caims.workload;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.solutions.caims.protocol.RequestEncryptionKeyPair;
import java.io.File;
import java.io.IOException;
import java.net.UnixDomainSocketAddress;
import java.nio.ByteBuffer;
import java.nio.channels.SocketChannel;
import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import org.jetbrains.annotations.NotNull;

public class ConfidentialSpace {
  /** Path to the Unix domain socket of the trusted execution environment server */
  private static final String TEE_SERVER_SOCKET_PATH = "/run/container_launcher/teeserver.sock";

  /** Endpoint of the token endpoint */
  private static final String TEE_TOKEN_ENDPOINT = "/v1/token";

  /** Maximum length (in characters) of a nonce */
  private static final int NONCE_LENGTH_MAX = 74;

  /** Minimum length (in characters) of a nonce */
  private static final int NONCE_LENGTH_MIN = 10;

  private static final Gson GSON = new GsonBuilder().create();

  /**
   * Request an attestation token from the TEE server. This method only works when used inside a
   * Confidential Space trusted execution environment.
   */
  public @NotNull AttestationToken getAttestationToken(
      @NotNull String audience, @NotNull List<String> nonces) throws IOException {
    if (!new File(TEE_SERVER_SOCKET_PATH).exists()) {
      throw new ConfidentialSpaceException(
          String.format(
              "TEE socket not found at %s, the most likely reason for "
                  + "that is that the workload server is executed outside a confidential"
                  + "space TEE",
              TEE_SERVER_SOCKET_PATH));
    }

    //
    // Java's built-in HTTP client doesn't support sending HTTP requests over a
    // Unix domain socket, so we need to use a plain TCP client to do the HTTP
    // exchange.
    //
    var address = UnixDomainSocketAddress.of(TEE_SERVER_SOCKET_PATH);

    var requestBody = new HashMap<String, Object>();
    requestBody.put("audience", audience);
    requestBody.put("token_type", "OIDC");
    requestBody.put("nonces", nonces);
    var requestBodyString = GSON.toJson(requestBody);

    try (var clientChannel = SocketChannel.open(address)) {
      //
      // Format an HTTP request.
      //
      // Use HTTP 1.0 so that we don't have to deal with chunked responses.
      //
      var httpRequest =
          String.format(
              "POST %s HTTP/1.0\r\n"
                  + "Host: localhost\r\n"
                  + "Connection: close\r\n"
                  + "Content-type: application/json\r\n"
                  + "Content-length: %d\r\n"
                  + "\r\n"
                  + "%s",
              TEE_TOKEN_ENDPOINT,
              requestBodyString.getBytes(StandardCharsets.UTF_8).length,
              requestBodyString);

      //
      // Write request to the channel.
      //
      writeString(clientChannel, httpRequest);

      //
      // Read response from channel.
      //
      var httpResponse = readString(clientChannel);

      //
      // Validate response and extract the response body.
      //
      if (!httpResponse.startsWith("HTTP/1.0 200 OK")) {
        System.err.printf(
            "[ERROR] Received unexpected response from TEE server: %s\n", httpResponse);
        throw new ConfidentialSpaceException("Received unexpected response from TEE server");
      }

      var body = Arrays.stream(httpResponse.split("\r\n\r\n")).skip(1).findFirst();
      if (body.isEmpty() || !body.get().startsWith("ey")) {
        System.err.printf(
            "[ERROR] Received empty or unexpected response from TEE server: %s\n", httpResponse);
        throw new ConfidentialSpaceException(
            "Received empty or unexpected response from TEE server");
      }

      return new AttestationToken(body.get().trim());
    }
  }

  /**
   * Request an attestation token from the TEE server with an embedded REK. This method only works
   * when used inside a Confidential Space trusted execution environment.
   */
  public @NotNull AttestationToken getAttestationToken(
      @NotNull String audience, @NotNull RequestEncryptionKeyPair.PublicKey key)
      throws IOException, GeneralSecurityException {

    //
    // To bind the workload server's REK to the attestation, we embed
    // it as a nonce.
    //
    // The most efficient way to embed the key would be to take its
    // uncompressed X and Y values (which are both 32 bytes in size,
    // translating to 43 characters in Base64) and embed them as two
    // nonces. However, doing so would break with Tink's notion of
    // treating keys as opaque blobs that not only contain key material
    // but also relevant parameters, so we're not doing that here.
    // Instead, we take the entire Tink key and serialize it, even if
    // that's less space-efficient.
    //
    // Because nonces have a maximum length that's shorter than the
    // serialized public key, we have to break it into multiple parts.
    //
    var encodedKey = key.toBase64();
    int textLength = encodedKey.length();

    //
    // Make sure that the last part doesn't become too short.
    //
    int partLength = NONCE_LENGTH_MAX;
    while ((encodedKey.length() % partLength) < NONCE_LENGTH_MIN) {
      partLength--;
    }

    var parts = new ArrayList<String>();
    int startIndex = 0;
    while (startIndex < textLength) {
      int endIndex = Math.min(startIndex + partLength, textLength);
      parts.add(encodedKey.substring(startIndex, endIndex));
      startIndex = endIndex;
    }

    return getAttestationToken(audience, parts);
  }

  private static void writeString(@NotNull SocketChannel channel, @NotNull String s)
      throws IOException {
    var buffer = ByteBuffer.wrap(s.getBytes(StandardCharsets.UTF_8));

    while (buffer.hasRemaining()) {
      channel.write(buffer);
    }
  }

  private static @NotNull String readString(@NotNull SocketChannel channel) throws IOException {
    var buffer = ByteBuffer.allocate(1024);
    var result = new StringBuilder();

    while (channel.read(buffer) != -1) {
      buffer.flip();
      result.append(StandardCharsets.UTF_8.decode(buffer));
      buffer.clear();
    }

    return result.toString();
  }
}
