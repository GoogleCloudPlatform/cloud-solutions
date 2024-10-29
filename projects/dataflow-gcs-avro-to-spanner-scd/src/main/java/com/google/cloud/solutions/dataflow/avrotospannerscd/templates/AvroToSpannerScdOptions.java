/*
 * Copyright (C) 2024 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License"); you may not
 * use this file except in compliance with the License. You may obtain a copy of
 * the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
 * WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
 * License for the specific language governing permissions and limitations under
 * the License.
 */

package com.google.cloud.solutions.dataflow.avrotospannerscd.templates;

import com.google.cloud.solutions.dataflow.avrotospannerscd.transforms.SpannerScdMutationTransform.ScdType;
import com.google.cloud.solutions.dataflow.avrotospannerscd.utils.StructHelper.StructComparator.SortOrder;
import com.google.cloud.spanner.Options.RpcPriority;
import java.util.List;
import org.apache.beam.sdk.extensions.gcp.options.GcpOptions;
import org.apache.beam.sdk.options.Default;
import org.apache.beam.sdk.options.Validation.Required;

/**
 * Options supported by the pipeline.
 *
 * <p>Inherits standard configuration options.
 */
public interface AvroToSpannerScdOptions extends GcpOptions {

  @Required
  String getInputFilePattern();

  void setInputFilePattern(String value);

  String getSpannerProjectId();

  void setSpannerProjectId(String value);

  @Required
  String getInstanceId();

  void setInstanceId(String value);

  @Required
  String getDatabaseId();

  void setDatabaseId(String value);

  @Required
  String getTableName();

  void setTableName(String value);

  RpcPriority getSpannerPriority();

  void setSpannerPriority(RpcPriority value);

  @Default.Integer(100)
  Integer getSpannerBatchSize();

  void setSpannerBatchSize(Integer value);

  @Default.Enum("TYPE_1")
  ScdType getScdType();

  void setScdType(ScdType value);

  @Required
  List<String> getPrimaryKeyColumnNames();

  void setPrimaryKeyColumnNames(List<String> value);

  String getOrderByColumnName();

  void setOrderByColumnName(String value);

  @Default.Enum("ASC")
  SortOrder getSortOrder();

  void setSortOrder(SortOrder value);

  String getStartDateColumnName();

  void setStartDateColumnName(String value);

  String getEndDateColumnName();

  void setEndDateColumnName(String value);
}
