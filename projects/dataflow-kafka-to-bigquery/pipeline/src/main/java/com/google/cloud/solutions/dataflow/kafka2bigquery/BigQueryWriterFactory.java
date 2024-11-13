package com.google.cloud.solutions.dataflow.kafka2bigquery;

import org.apache.beam.sdk.io.gcp.bigquery.BigQueryIO;

/**
 * Factory to create BigQueryIO.Write instances, allowing easy injection of BigQueryServices for
 * testing.
 */
public interface BigQueryWriterFactory {

  /**
   * Creates a writer instance based on the PCollection's type.
   *
   * @param collectionClass the type of PCollection.
   * @param <T> the type of PCollection.
   */
  <T> BigQueryIO.Write<T> get(Class<T> collectionClass);
}
