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

import com.google.crypto.tink.*;
import com.google.crypto.tink.hybrid.HybridKeyTemplates;
import com.google.crypto.tink.proto.KeyTemplate;
import com.google.crypto.tink.subtle.Base64;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.security.GeneralSecurityException;
import org.jetbrains.annotations.NotNull;

/** A (typically ephemeral) key pair for encrypting requests. */
public class RequestEncryptionKeyPair {
  /**
   * Key type to use for hybrid encryption.
   *
   * <ul>
   *   <li>Key encapsulation (KEM): Diffie-Hellman using P-256 curve
   *   <li>Key Derivation (KDF): HMAC-SHA256
   *   <li>Authenticated Encryption with Associated Data (AEAD): AES-128 GCM
   * </ul>
   */
  private static final @NotNull KeyTemplate TEMPLATE =
      HybridKeyTemplates.ECIES_P256_HKDF_HMAC_SHA256_AES128_GCM;

  private final @NotNull PublicKey publicKey;
  private final @NotNull PrivateKey privateKey;

  /** Get the public key part of te key pair. */
  public @NotNull PublicKey publicKey() {
    return publicKey;
  }

  /** Get the private key part of te key pair. */
  public @NotNull PrivateKey privateKey() {
    return privateKey;
  }

  private RequestEncryptionKeyPair(@NotNull PrivateKey privateKey, @NotNull PublicKey publicKey) {
    this.publicKey = publicKey;
    this.privateKey = privateKey;
  }

  /** Generate a new key pair. */
  public static @NotNull RequestEncryptionKeyPair generate() throws GeneralSecurityException {
    var handle = KeysetHandle.generateNew(TEMPLATE);

    return new RequestEncryptionKeyPair(
        new PrivateKey(handle), new PublicKey(handle.getPublicKeysetHandle()));
  }

  // ---------------------------------------------------------------------------
  // Inner classes.
  // ---------------------------------------------------------------------------

  /** Public portion of the key pair. */
  public static class PublicKey {
    private final @NotNull KeysetHandle handle;

    /** Get the key's parameters. */
    Parameters parameters() {
      return this.handle.getPrimary().getKey().getParameters();
    }

    private PublicKey(@NotNull KeysetHandle handle) {
      this.handle = handle;
    }

    /** Use the public key to encrypt a piece of clear text. */
    public byte[] encrypt(byte[] clearText) throws GeneralSecurityException {
      return this.handle
          .getPrimitive(RegistryConfiguration.get(), HybridEncrypt.class)
          .encrypt(clearText, null);
    }

    /** Serialize key using Tink's native format. */
    byte[] toByteArray() throws GeneralSecurityException {
      return TinkProtoKeysetFormat.serializeKeysetWithoutSecret(this.handle);
    }

    /** Serialize key using Tink's native format and wrap it as Base64. */
    public @NotNull String toBase64() throws GeneralSecurityException {
      return Base64.encode(toByteArray());
    }

    /** Create public key from the format created by {@see toBase64}. */
    public static @NotNull PublicKey fromBase64(@NotNull String key)
        throws GeneralSecurityException {
      return new PublicKey(TinkProtoKeysetFormat.parseKeysetWithoutSecret(Base64.decode(key)));
    }

    /** Serialize key using Tink's native format and write it to a stream. */
    static @NotNull PublicKey read(@NotNull DataInputStream stream)
        throws GeneralSecurityException, IOException {
      var size = stream.readInt();
      if (size == 0) {
        throw new IOException("The stream does not contain a valid key");
      }

      var keySet = TinkProtoKeysetFormat.parseKeysetWithoutSecret(stream.readNBytes(size));
      return new PublicKey(keySet);
    }

    /** Read a serialized key from a stream. */
    void write(@NotNull DataOutputStream stream) throws GeneralSecurityException, IOException {
      var serialized = toByteArray();
      stream.writeInt(serialized.length);
      stream.write(serialized);
    }

    @Override
    public boolean equals(Object obj) {
      return obj instanceof PublicKey other && this.handle.equalsKeyset(other.handle);
    }
  }

  /** Private portion of the key pair. */
  public static class PrivateKey {
    private final @NotNull KeysetHandle handle;

    private PrivateKey(@NotNull KeysetHandle handle) {
      this.handle = handle;
    }

    /**
     * Use the private key to decrypt a piece of clear text and, optionally a piece of associated
     * data.
     */
    public byte[] decrypt(byte[] cipherText) throws GeneralSecurityException {
      return this.handle
          .getPrimitive(RegistryConfiguration.get(), HybridDecrypt.class)
          .decrypt(cipherText, null);
    }
  }
}
