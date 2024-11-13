package com.google.cloud.solutions.dataflow.kafka2bigquery;

import org.apache.beam.sdk.io.gcp.bigquery.BigQueryIO.Write;
import org.apache.beam.sdk.io.gcp.bigquery.BigQueryServices;

/** Sets the provided BigQueryServices for enabling tests on the BigQuery writer. */
public final class TestServiceBigQueryWriterFactory implements BigQueryWriterFactory {

  private final BigQueryServices bigQueryServices;
  private final DefaultBigQueryWriterFactory defaultBigQueryWriterFactory;

  public TestServiceBigQueryWriterFactory(BigQueryServices bigQueryServices) {
    this.bigQueryServices = bigQueryServices;
    this.defaultBigQueryWriterFactory = new DefaultBigQueryWriterFactory();
  }

  public static TestServiceBigQueryWriterFactory create(BigQueryServices bigQueryServices) {
    return new TestServiceBigQueryWriterFactory(bigQueryServices);
  }

  @Override
  public <T> Write<T> get(Class<T> collectionClass) {
    return defaultBigQueryWriterFactory.get(collectionClass).withTestServices(bigQueryServices);
  }
}
