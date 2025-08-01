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

package com.google.solutions.caims.protocol;

import static org.junit.jupiter.api.Assertions.*;

import com.google.crypto.tink.hybrid.EciesParameters;
import com.google.crypto.tink.hybrid.HybridConfig;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

public class RequestEncryptionKeyPairTest {

  @BeforeAll
  public static void setup() throws Exception {
    HybridConfig.register();
  }

  // ---------------------------------------------------------------------------
  // generate.
  // ---------------------------------------------------------------------------

  @Test
  public void generate_createsPublicAndPrivateKey() throws Exception {
    var pair = RequestEncryptionKeyPair.generate();
    assertNotNull(pair.privateKey());
    assertNotNull(pair.publicKey());
  }

  @Test
  public void generate_usesP256() throws Exception {
    var parameters = RequestEncryptionKeyPair.generate().publicKey().parameters();
    var ecies = assertInstanceOf(EciesParameters.class, parameters);

    assertEquals(EciesParameters.CurveType.NIST_P256, ecies.getCurveType());
  }

  // ---------------------------------------------------------------------------
  // publicKey.
  // ---------------------------------------------------------------------------

  @Test
  public void publicKey_encrypt() throws Exception {
    var pair = RequestEncryptionKeyPair.generate();

    var clearText = "test".getBytes(StandardCharsets.US_ASCII);
    var cipherText = pair.publicKey().encrypt(clearText);

    var decrypted = pair.privateKey().decrypt(cipherText);

    assertArrayEquals(clearText, decrypted);
  }

  @Test
  public void publicKey_write() throws Exception {
    try (var buffer = new ByteArrayOutputStream();
        var stream = new DataOutputStream(buffer)) {
      RequestEncryptionKeyPair.generate().publicKey().write(stream);

      assertNotEquals(0, buffer.size());
    }
  }

  @Test
  public void publicKey_read() throws Exception {
    try (var buffer = new ByteArrayOutputStream()) {
      try (var stream = new DataOutputStream(buffer)) {
        RequestEncryptionKeyPair.generate().publicKey().write(stream);
      }

      try (var stream = new DataInputStream(new ByteArrayInputStream(buffer.toByteArray()))) {
        var publicKey = RequestEncryptionKeyPair.PublicKey.read(stream);

        assertNotNull(publicKey);
      }
    }
  }

  @ParameterizedTest
  @ValueSource(ints = {0, 1, 3})
  public void publicKey_read_whenDataInvalid(int size) throws Exception {
    try (var stream = new DataInputStream(new ByteArrayInputStream(new byte[size]))) {
      assertThrows(IOException.class, () -> RequestEncryptionKeyPair.PublicKey.read(stream));
    }
  }

  @Test
  public void publicKey_toBase64() throws Exception {
    var key = RequestEncryptionKeyPair.generate().publicKey();

    var serialized = key.toBase64();
    assertNotNull(serialized);

    var deserialized = RequestEncryptionKeyPair.PublicKey.fromBase64(serialized);
    assertEquals(key, deserialized);
  }

  // ---------------------------------------------------------------------------
  // privateKey.
  // ---------------------------------------------------------------------------

  @Test
  public void privateKey_decrypt_whenKeyDoesNotMatch() throws Exception {
    var pair = RequestEncryptionKeyPair.generate();

    var clearText = "test".getBytes(StandardCharsets.US_ASCII);
    var cipherText = pair.publicKey().encrypt(clearText);

    assertThrows(
        GeneralSecurityException.class,
        () -> RequestEncryptionKeyPair.generate().privateKey().decrypt(cipherText));
  }
}
