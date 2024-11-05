/*
 * Copyright 2023 Google LLC
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

package com.google.cloud.solutions.satools.common.testing.stubs.storage;

import com.google.api.gax.paging.Page;
import com.google.cloud.Policy;
import com.google.cloud.ReadChannel;
import com.google.cloud.WriteChannel;
import com.google.cloud.solutions.satools.common.testing.stubs.PatchyStub;
import com.google.cloud.storage.Acl;
import com.google.cloud.storage.Blob;
import com.google.cloud.storage.BlobId;
import com.google.cloud.storage.BlobInfo;
import com.google.cloud.storage.Bucket;
import com.google.cloud.storage.BucketInfo;
import com.google.cloud.storage.CopyWriter;
import com.google.cloud.storage.HmacKey;
import com.google.cloud.storage.Notification;
import com.google.cloud.storage.NotificationInfo;
import com.google.cloud.storage.PostPolicyV4;
import com.google.cloud.storage.ServiceAccount;
import com.google.cloud.storage.Storage;
import com.google.cloud.storage.StorageBatch;
import com.google.cloud.storage.StorageOptions;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.URL;
import java.nio.file.Path;
import java.util.List;
import java.util.concurrent.TimeUnit;

/** Fake Google Cloud Storage Client. */
public class PatchyStorage implements Storage {

  private final PatchyStub patchyStub;

  public PatchyStorage(PatchyStub patchyStub) {
    this.patchyStub = patchyStub;
  }

  @Override
  public Bucket create(BucketInfo bucketInfo, BucketTargetOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Blob create(BlobInfo blobInfo, BlobTargetOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Blob create(BlobInfo blobInfo, byte[] content, BlobTargetOption... options) {
    return patchyStub
        .findCallable(
            CreateBlobRequest.class,
            Blob.class,
            () -> {
              throw new UnsupportedOperationException("my lambda");
            })
        .call(new CreateBlobRequest(blobInfo, content, options));
  }

  @Override
  public Blob create(
      BlobInfo blobInfo, byte[] content, int offset, int length, BlobTargetOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Blob create(BlobInfo blobInfo, InputStream content, BlobWriteOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Blob createFrom(BlobInfo blobInfo, Path path, BlobWriteOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Blob createFrom(BlobInfo blobInfo, Path path, int bufferSize, BlobWriteOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Blob createFrom(BlobInfo blobInfo, InputStream content, BlobWriteOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Blob createFrom(
      BlobInfo blobInfo, InputStream content, int bufferSize, BlobWriteOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Blob get(String bucket, String blob, BlobGetOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Blob get(BlobId blob, BlobGetOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Blob get(BlobId blob) {
    throw new UnsupportedOperationException();
  }

  @Override
  public List<Blob> get(BlobId... blobIds) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Bucket get(String bucket, BucketGetOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public List<Blob> get(Iterable<BlobId> blobIds) {
    throw new UnsupportedOperationException();
  }

  @Override
  public List<Blob> update(BlobInfo... blobInfos) {
    throw new UnsupportedOperationException();
  }

  @Override
  public List<Blob> update(Iterable<BlobInfo> blobInfos) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Bucket update(BucketInfo bucketInfo, BucketTargetOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Blob update(BlobInfo blobInfo, BlobTargetOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Blob update(BlobInfo blobInfo) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Bucket lockRetentionPolicy(BucketInfo bucket, BucketTargetOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Page<Bucket> list(BucketListOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Page<Blob> list(String bucket, BlobListOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public boolean delete(String bucket, BucketSourceOption... options) {
    return false;
  }

  @Override
  public boolean delete(String bucket, String blob, BlobSourceOption... options) {
    return false;
  }

  @Override
  public boolean delete(BlobId blob, BlobSourceOption... options) {
    return false;
  }

  @Override
  public boolean delete(BlobId blob) {
    return false;
  }

  @Override
  public List<Boolean> delete(BlobId... blobIds) {
    throw new UnsupportedOperationException();
  }

  @Override
  public List<Boolean> delete(Iterable<BlobId> blobIds) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Blob compose(ComposeRequest composeRequest) {
    throw new UnsupportedOperationException();
  }

  @Override
  public CopyWriter copy(CopyRequest copyRequest) {
    throw new UnsupportedOperationException();
  }

  @Override
  public byte[] readAllBytes(String bucket, String blob, BlobSourceOption... options) {
    return new byte[0];
  }

  @Override
  public byte[] readAllBytes(BlobId blob, BlobSourceOption... options) {
    return new byte[0];
  }

  @Override
  public StorageBatch batch() {
    throw new UnsupportedOperationException();
  }

  @Override
  public ReadChannel reader(String bucket, String blob, BlobSourceOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public ReadChannel reader(BlobId blob, BlobSourceOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public void downloadTo(BlobId blob, Path path, BlobSourceOption... options) {}

  @Override
  public void downloadTo(BlobId blob, OutputStream outputStream, BlobSourceOption... options) {}

  @Override
  public WriteChannel writer(BlobInfo blobInfo, BlobWriteOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public WriteChannel writer(URL signedUrl) {
    throw new UnsupportedOperationException();
  }

  @Override
  public URL signUrl(BlobInfo blobInfo, long duration, TimeUnit unit, SignUrlOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public PostPolicyV4 generateSignedPostPolicyV4(
      BlobInfo blobInfo,
      long duration,
      TimeUnit unit,
      PostPolicyV4.PostFieldsV4 fields,
      PostPolicyV4.PostConditionsV4 conditions,
      PostPolicyV4Option... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public PostPolicyV4 generateSignedPostPolicyV4(
      BlobInfo blobInfo,
      long duration,
      TimeUnit unit,
      PostPolicyV4.PostFieldsV4 fields,
      PostPolicyV4Option... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public PostPolicyV4 generateSignedPostPolicyV4(
      BlobInfo blobInfo,
      long duration,
      TimeUnit unit,
      PostPolicyV4.PostConditionsV4 conditions,
      PostPolicyV4Option... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public PostPolicyV4 generateSignedPostPolicyV4(
      BlobInfo blobInfo, long duration, TimeUnit unit, PostPolicyV4Option... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Acl getAcl(String bucket, Acl.Entity entity, BucketSourceOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Acl getAcl(String bucket, Acl.Entity entity) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Acl getAcl(BlobId blob, Acl.Entity entity) {
    throw new UnsupportedOperationException();
  }

  @Override
  public boolean deleteAcl(String bucket, Acl.Entity entity, BucketSourceOption... options) {
    return false;
  }

  @Override
  public boolean deleteAcl(String bucket, Acl.Entity entity) {
    return false;
  }

  @Override
  public boolean deleteAcl(BlobId blob, Acl.Entity entity) {
    return false;
  }

  @Override
  public Acl createAcl(String bucket, Acl acl, BucketSourceOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Acl createAcl(String bucket, Acl acl) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Acl createAcl(BlobId blob, Acl acl) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Acl updateAcl(String bucket, Acl acl, BucketSourceOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Acl updateAcl(String bucket, Acl acl) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Acl updateAcl(BlobId blob, Acl acl) {
    throw new UnsupportedOperationException();
  }

  @Override
  public List<Acl> listAcls(String bucket, BucketSourceOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public List<Acl> listAcls(String bucket) {
    throw new UnsupportedOperationException();
  }

  @Override
  public List<Acl> listAcls(BlobId blob) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Acl getDefaultAcl(String bucket, Acl.Entity entity) {
    throw new UnsupportedOperationException();
  }

  @Override
  public boolean deleteDefaultAcl(String bucket, Acl.Entity entity) {
    return false;
  }

  @Override
  public Acl createDefaultAcl(String bucket, Acl acl) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Acl updateDefaultAcl(String bucket, Acl acl) {
    throw new UnsupportedOperationException();
  }

  @Override
  public List<Acl> listDefaultAcls(String bucket) {
    throw new UnsupportedOperationException();
  }

  @Override
  public HmacKey createHmacKey(ServiceAccount serviceAccount, CreateHmacKeyOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Page<HmacKey.HmacKeyMetadata> listHmacKeys(ListHmacKeysOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public HmacKey.HmacKeyMetadata getHmacKey(String accessId, GetHmacKeyOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public void deleteHmacKey(
      HmacKey.HmacKeyMetadata hmacKeyMetadata, DeleteHmacKeyOption... options) {}

  @Override
  public HmacKey.HmacKeyMetadata updateHmacKeyState(
      HmacKey.HmacKeyMetadata hmacKeyMetadata,
      HmacKey.HmacKeyState state,
      UpdateHmacKeyOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Policy getIamPolicy(String bucket, BucketSourceOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Policy setIamPolicy(String bucket, Policy policy, BucketSourceOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public List<Boolean> testIamPermissions(
      String bucket, List<String> permissions, BucketSourceOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public ServiceAccount getServiceAccount(String projectId) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Notification createNotification(String bucket, NotificationInfo notificationInfo) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Notification getNotification(String bucket, String notificationId) {
    throw new UnsupportedOperationException();
  }

  @Override
  public List<Notification> listNotifications(String bucket) {
    throw new UnsupportedOperationException();
  }

  @Override
  public boolean deleteNotification(String bucket, String notificationId) {
    return false;
  }

  @Override
  public StorageOptions getOptions() {
    throw new UnsupportedOperationException();
  }
}
