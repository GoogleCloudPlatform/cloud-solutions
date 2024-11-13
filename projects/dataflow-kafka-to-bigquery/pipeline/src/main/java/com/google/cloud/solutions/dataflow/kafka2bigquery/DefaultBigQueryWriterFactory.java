package com.google.cloud.solutions.dataflow.kafka2bigquery;

import static com.google.common.base.Preconditions.checkNotNull;

import com.google.api.services.bigquery.model.TableRow;
import com.google.protobuf.Message;
import org.apache.beam.sdk.io.gcp.bigquery.BigQueryIO;
import org.apache.beam.sdk.io.gcp.bigquery.BigQueryIO.Write;

/**
 * Factory to build {@link org.apache.beam.sdk.io.gcp.bigquery.BigQueryIO.Write} objects based on
 * type.
 */
public class DefaultBigQueryWriterFactory implements BigQueryWriterFactory {

  @Override
  public <T> Write<T> get(Class<T> collectionClass) {
    checkNotNull(collectionClass, "PCollection Class can't be null");

    if (TableRow.class == collectionClass) {
      return (BigQueryIO.Write<T>) BigQueryIO.writeTableRows();
    } else if (Message.class.isAssignableFrom(collectionClass)) {
      return (BigQueryIO.Write<T>) BigQueryIO.writeProtos((Class<Message>) collectionClass);
    }

    return BigQueryIO.write();
  }
}
