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

/** @fileoverview Tests state-firestore. */

// eslint-disable-next-line n/no-unpublished-import
import 'jasmine';
import {FirestoreStateStore, FirestoreStateData} from '../state-firestore';
import {ScalableInstanceWithData} from '../../../common/instance-info';
import {
  DocumentReference,
  DocumentData,
  DocumentSnapshot,
  Firestore,
  Timestamp,
  UpdateData,
  WriteResult,
  Precondition,
} from '@google-cloud/firestore';
import {TEST_INSTANCE_WITH_DATA} from '../../../testing/testing-data';

/** Types for Firestore mocks. */
type DbModelType = DocumentData;
type DocUpdateSpy = (
  data: UpdateData<DbModelType>,
  precondition?: Precondition
) => Promise<WriteResult>;

/** Sample instance with Firestore stateConfig for testing. */
const SAMPLE_INSTANCE: ScalableInstanceWithData = Object.freeze({
  ...TEST_INSTANCE_WITH_DATA,
  stateConfig: Object.freeze({
    stateProjectId: 'project-2',
    stateDatabase: Object.freeze({
      name: 'firestore',
      instanceId: 'state-instance',
      databaseId: 'state-database',
    }),
  }),
});

/** Sample document data. */
const SAMPLE_DOC_DATA: FirestoreStateData = {
  createdOn: Timestamp.fromMillis(1_000_000),
  updatedOn: Timestamp.fromMillis(2_000_000),
  lastScalingTimestamp: Timestamp.fromMillis(3_000_000),
  lastScalingCompleteTimestamp: Timestamp.fromMillis(4_000_000),
  scalingRequestedSize: null,
  scalingOperationId: null,
};

describe('FirestoreStateStore', () => {
  let firestoreMockProvider: FirestoreMockProvider;
  let firestoreClient: Firestore;
  let firestoreStateStore: FirestoreStateStore;

  beforeEach(() => {
    jasmine
      .clock()
      .install()
      .mockDate(new Date(Math.pow(10, 7)));

    firestoreMockProvider = new FirestoreMockProvider();
    firestoreClient = firestoreMockProvider.getFirestoreMock();
    firestoreStateStore = new FirestoreStateStore(
      SAMPLE_INSTANCE,
      'autoscaler',
      firestoreClient
    );
  });

  afterEach(() => {
    jasmine.clock().uninstall();
  });

  describe('init', () => {
    it('sets and returns default data', async () => {
      const docRefMock = firestoreMockProvider.getDocRefMock();

      const output = await firestoreStateStore.init();

      const expectedInitData: FirestoreStateData = {
        createdOn: Timestamp.fromMillis(10_000_000),
        updatedOn: Timestamp.fromMillis(10_000_000),
        lastScalingTimestamp: Timestamp.fromMillis(0),
        lastScalingCompleteTimestamp: Timestamp.fromMillis(0),
        scalingOperationId: null,
        scalingRequestedSize: null,
        scalingPreviousSize: null,
        scalingMethod: null,
      };
      expect(docRefMock.set).toHaveBeenCalledOnceWith(expectedInitData);
      expect(output).toEqual(expectedInitData);
    });
  });

  describe('getState', () => {
    it('queries expected document', async () => {
      const firestoreMock = firestoreMockProvider.getFirestoreMock();

      await firestoreStateStore.getState();

      expect(firestoreMock.doc).toHaveBeenCalledOnceWith(
        'autoscaler/state/projects/project-123/locations/us-central1'
      );
    });

    it('returns document details, if document data exists', async () => {
      const docMock = firestoreMockProvider.getDocMock();
      Object.defineProperty(docMock, 'exists', {value: true});
      docMock.data.and.returnValue(SAMPLE_DOC_DATA);

      const output = await firestoreStateStore.getState();

      expect(output).toEqual({
        createdOn: 1_000_000,
        updatedOn: 2_000_000,
        lastScalingTimestamp: 3_000_000,
        lastScalingCompleteTimestamp: 4_000_000,
        scalingRequestedSize: null,
        scalingOperationId: null,
        scalingPreviousSize: null,
        scalingMethod: null,
      });
    });

    it('gets default data, if document data does not exist', async () => {
      const docMock = firestoreMockProvider.getDocMock();
      Object.defineProperty(docMock, 'exists', {value: false});

      const output = await firestoreStateStore.getState();

      expect(output).toEqual({
        createdOn: 10_000_000,
        updatedOn: 10_000_000,
        lastScalingTimestamp: 0,
        lastScalingCompleteTimestamp: 0,
        scalingRequestedSize: null,
        scalingOperationId: null,
        scalingPreviousSize: null,
        scalingMethod: null,
      });
    });
  });

  describe('updateState', () => {
    it('writes the state data to the document', async () => {
      const docRefMock = firestoreMockProvider.getDocRefMock();
      const docMock = firestoreMockProvider.getDocMock();
      Object.defineProperty(docMock, 'exists', {value: false});

      await firestoreStateStore.updateState({
        lastScalingTimestamp: 999_999,
        lastScalingCompleteTimestamp: 1_000_000,
        scalingOperationId: 'xyz',
        scalingPreviousSize: 3,
        scalingRequestedSize: 5,
        scalingMethod: 'DIRECT',
        // This will be deleted. Normally, this parameter will not be present on
        // the real call, but this helps to test this behaviour.
        createdOn: 123,
      });

      expect(docRefMock.update as DocUpdateSpy).toHaveBeenCalledOnceWith({
        updatedOn: Timestamp.fromMillis(10_000_000),
        lastScalingTimestamp: Timestamp.fromMillis(999_999),
        lastScalingCompleteTimestamp: Timestamp.fromMillis(1_000_000),
        scalingOperationId: 'xyz',
        scalingPreviousSize: 3,
        scalingRequestedSize: 5,
        scalingMethod: 'DIRECT',
      });
    });
  });
});

class FirestoreMockProvider {
  private firestoreClientMock: jasmine.SpyObj<Firestore>;
  private firestoreDocRefMock: jasmine.SpyObj<DocumentReference>;
  private firestoreDocMock: jasmine.SpyObj<
    DocumentSnapshot<DocumentData, DocumentData>
  >;

  constructor() {
    this.firestoreDocMock = jasmine.createSpyObj<
      DocumentSnapshot<DocumentData, DocumentData>
    >(
      'DocumentSnapshot',
      ['data']
      // , ['exists'] - Mock on each individual test.
    );

    this.firestoreDocRefMock = jasmine.createSpyObj<DocumentReference>(
      'DocumentReference',
      {
        set: jasmine.createSpy(),
        get: this.firestoreDocMock,
        update: jasmine.createSpy(),
      } as any // eslint-disable-line @typescript-eslint/no-explicit-any
    );
    this.firestoreClientMock = jasmine.createSpyObj<Firestore>('Firestore', {
      doc: this.firestoreDocRefMock,
    });
  }

  getFirestoreMock() {
    return this.firestoreClientMock;
  }

  getDocRefMock() {
    return this.firestoreDocRefMock;
  }

  getDocMock() {
    return this.firestoreDocMock;
  }
}
