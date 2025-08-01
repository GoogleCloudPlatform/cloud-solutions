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

import com.google.crypto.tink.hybrid.HybridConfig;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

public class MessageTest {

  @BeforeAll
  public static void setup() throws Exception {
    HybridConfig.register();
  }

  // ---------------------------------------------------------------------------
  // toString.
  // ---------------------------------------------------------------------------

  @Test
  public void toString_returnsClearText() {
    var message = new Message("Test", null);
    assertEquals("Test", message.toString());
  }

  // ---------------------------------------------------------------------------
  // encrypt.
  // ---------------------------------------------------------------------------

  @Test
  public void encrypt_withoutSenderPublicKey() throws Exception {
    var recipientKeyPair = RequestEncryptionKeyPair.generate();

    var message = new Message("Test", null);
    var decryptedMessage =
        message.encrypt(recipientKeyPair.publicKey()).decrypt(recipientKeyPair.privateKey());

    assertEquals("Test", decryptedMessage.toString());
    assertFalse(decryptedMessage.senderPublicKey().isPresent());
  }

  @Test
  public void encrypt_withSenderPublicKey() throws Exception {
    var recipientKeyPair = RequestEncryptionKeyPair.generate();
    var senderKeyPair = RequestEncryptionKeyPair.generate();

    var message = new Message("Test", senderKeyPair.publicKey());
    var decryptedMessage =
        message.encrypt(recipientKeyPair.publicKey()).decrypt(recipientKeyPair.privateKey());

    assertEquals("Test", decryptedMessage.toString());
    assertNotNull(decryptedMessage.senderPublicKey());
    assertEquals(decryptedMessage.senderPublicKey().get(), senderKeyPair.publicKey());
  }
}
