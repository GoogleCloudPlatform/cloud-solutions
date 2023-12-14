// Copyright 2023 Google LLC
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package main

import (
	"context"
	"os"

	"com.google.cloud.solutions.satools/pt-admin/internal"
	"sigs.k8s.io/controller-runtime/pkg/log"
	"sigs.k8s.io/controller-runtime/pkg/log/zap"
)

func main() {

	opts := zap.Options{
		Development: false,
		DestWriter:  os.Stdout,
	}
	l := zap.New(zap.UseFlagOptions(&opts))
	log.SetLogger(l)
	l.Info("starting pt-admin")
	internal.Router(context.Background()).Run("0.0.0.0:9080")

}
