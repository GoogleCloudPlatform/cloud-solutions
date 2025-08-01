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

import java.io.ByteArrayInputStream;
import java.io.DataInputStream;
import java.io.IOException;
import java.security.GeneralSecurityException;
import org.jetbrains.annotations.NotNull;

/**
 * A message that has been encrypted by a sender and can only be decrypted by the intended receiver.
 *
 * <p>If the message represents a request, then the sender is the client, and the recipient is the
 * server. If the message represents a response, the roles are reversed.
 *
 * @param cipherText Message body, encrypted.
 */
public record EncryptedMessage(byte[] cipherText) {

  /** Get raw cipher text. */
  @Override
  public byte[] cipherText() {
    return cipherText;
  }

  /** Decrypt the message using the recipient's private key. */
  public @NotNull Message decrypt(@NotNull RequestEncryptionKeyPair.PrivateKey recipientPrivateKey)
      throws GeneralSecurityException, IOException {
    var clearText = recipientPrivateKey.decrypt(this.cipherText);

    try (var stream = new DataInputStream(new ByteArrayInputStream(clearText))) {
      var body = stream.readUTF();

      var senderPublicKey =
          stream.available() > 0 ? RequestEncryptionKeyPair.PublicKey.read(stream) : null;

      return new Message(body, senderPublicKey);
    }
  }
}
