/**
 * Copyright 2024 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

/** @file Provides functionality to work with Protobuf messages. */

import protobuf from 'protobufjs';

export class ProtobufEncoder {
  /** Protobuf message type. Message Type is lazy loaded when needed. */
  protected messageType?: protobuf.Type;

  /**
   * Initializes Protobuf encoder with the protobuf schema.
   * @param protobufPath Path to the protobuf schema.
   * @param messageName Name of the type of the message from the schema.
   */
  constructor(
    protected protobufPath: string,
    protected messageName: string
  ) {}

  /**
   * Encodes JSON data to the Protobuf schema.
   * @param jsonData JSON data to encode to protobuf.
   * @return Data encoded as a Protobuf message.
   */
  async encodeDataAsProtobufMessage(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    jsonData: Record<string, any>
  ): Promise<protobuf.Message> {
    if (!this.messageType) this.messageType = await this.getProtoSchema();
    return this.messageType.create(jsonData);
  }

  /** Gets the protobuf message type for encoding data. */
  private async getProtoSchema(): Promise<protobuf.Type> {
    const protobufSchema = await protobuf.load(this.protobufPath);
    return protobufSchema.lookupType(this.messageName);
  }
}
