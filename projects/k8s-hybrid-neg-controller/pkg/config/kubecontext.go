// Copyright 2024 Google LLC
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

package config

import (
	"k8s.io/client-go/tools/clientcmd"
)

const (
	// See k8s.io/client-go/tools/clientcmd.FlagContext.
	kubecontextFlagName = "context"
)

var kubecontext string

func init() {
	commandLine.StringVar(&kubecontext, kubecontextFlagName, "", "The name of the kubeconfig context to use, if using a kubeconfig file."+
		" If unset, the current context will be used. See also the '"+clientcmd.RecommendedConfigPathFlag+"' flag.")
}
