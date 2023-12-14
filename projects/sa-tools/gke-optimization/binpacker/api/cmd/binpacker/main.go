// Copyright 2023 Google LLC
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package main

import (
	"context"
	"flag"
	"log"
	"net/http"
	"os"
	"strconv"
	"time"

	"github.com/golang/glog"
	"golang.org/x/oauth2/google"

	"github.com/GoogleCloudPlatform/cloud-solutions/projects/sa-tools/gke_optimization/binpacker/api/pkg/infrastructure/repository/metric/kubeapi"
	"github.com/GoogleCloudPlatform/cloud-solutions/projects/sa-tools/gke_optimization/binpacker/api/pkg/interface/handler"
	"github.com/GoogleCloudPlatform/cloud-solutions/projects/sa-tools/gke_optimization/binpacker/api/pkg/usecase"

	"github.com/julienschmidt/httprouter"
	"github.com/rs/cors"
)

const DefaultPort = 8080

func main() {
	// This is needed to use glog
	flag.Parse()

	_, err := google.FindDefaultCredentials(context.Background())
	if err != nil {
		glog.Fatalf("Failed to find application default credential: %s", err.Error())
	}

	binpackingUsecase := usecase.NewBinpackingUsecase()
	binpackingHandler := handler.NewBinpackingHandler(binpackingUsecase)

	metricRepository := kubeapi.NewMetricKubeapiRepository()
	metricUsecase := usecase.NewMetricUsecase(metricRepository)
	metricHandler := handler.NewMetricHandler(metricUsecase)

	router := httprouter.New()
	router.POST("/api/binpacker", binpackingHandler.Calculate)
	router.POST("/api/metrics", metricHandler.FetchAll)
	router.OPTIONS("/*path", handleOption)

	static := httprouter.New()
	static.ServeFiles("/*filepath", http.Dir("./static"))
	router.NotFound = static

	corsHandler := cors.Default().Handler(router)

	port := getPort()
	glog.Infof("Binpacker started on port: %d", port)

	server := &http.Server{
		Addr:              ":" + strconv.Itoa(port),
		ReadHeaderTimeout: 60 * time.Second,
		Handler:           corsHandler,
	}
	log.Fatal(server.ListenAndServe())
}

func handleOption(w http.ResponseWriter, _ *http.Request, _ httprouter.Params) {
	w.Header().Add("Access-Control-Allow-Origin", "*")
	w.Header().Set("Access-Control-Allow-Methods", "*")
	w.Header().Add("Access-Control-Allow-Headers", "Content-Type")
	w.Header().Add("Access-Control-Allow-Headers", "Origin")
	w.Header().Add("Access-Control-Allow-Headers", "X-Requested-With")
	w.Header().Add("Access-Control-Allow-Headers", "Accept")
	w.Header().Add("Access-Control-Allow-Headers", "Accept-Language")
	w.Header().Set("Content-Type", "application/json")
}

func getPort() int {
	port := os.Getenv("PORT")
	if port == "" {
		return DefaultPort
	}

	portNum, err := strconv.Atoi(port)
	if err != nil || !isValidPortNumber(portNum) {
		glog.Infof("Invalid port %s is specified. Fallback to default port number: %d", port, DefaultPort)
		return DefaultPort
	}
	return portNum
}

func isValidPortNumber(portNum int) bool {
	return 1023 < portNum && portNum < 65536
}
