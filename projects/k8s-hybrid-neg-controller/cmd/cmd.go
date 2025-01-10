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

package cmd

import (
	"context"
	"errors"
	"flag"
	"fmt"
	"strings"

	"github.com/spf13/pflag"
	"github.com/spf13/viper"
	"k8s.io/klog/v2"
	ctrl "sigs.k8s.io/controller-runtime"
	clientconfig "sigs.k8s.io/controller-runtime/pkg/client/config"

	"github.com/googlecloudplatform/k8s-hybrid-neg-controller/pkg/auth"
	"github.com/googlecloudplatform/k8s-hybrid-neg-controller/pkg/config"
	"github.com/googlecloudplatform/k8s-hybrid-neg-controller/pkg/manager"
	"github.com/googlecloudplatform/k8s-hybrid-neg-controller/pkg/reconciler"
)

const (
	EventRecorderName = "hybrid-neg-controller"
)

// Run starts the controller manager.
func Run(ctx context.Context, flagset *flag.FlagSet, args []string) error {
	ctx, cancel := context.WithCancel(ctx)
	defer cancel()

	if err := initFlags(flagset, args); err != nil {
		return err
	}

	logger := klog.NewKlogr()
	ctrl.SetLogger(logger)
	auth.RegisterGoogle(ctx, logger)

	configClient, err := config.NewClient(ctx)
	if err != nil {
		return fmt.Errorf("could not create controller manager configuration client: %w", err)
	}
	managerConfig := configClient.GetManagerConfig()
	reconcilerConfig, err := configClient.GetReconcilerConfig(ctx, logger)
	if err != nil {
		return fmt.Errorf("problem getting reconciler configuration: %w", err)
	}
	logger.V(4).Info("Controller configuration", "manager", managerConfig, "reconciler", reconcilerConfig)

	mgr, err := manager.NewManager(managerConfig)
	if err != nil {
		return fmt.Errorf("problem creating controller manager: %w", err)
	}

	eventRecorder := mgr.GetEventRecorderFor(EventRecorderName)
	if err := reconciler.CreateReconcilers(ctx, mgr, eventRecorder, reconcilerConfig); err != nil {
		return err
	}

	logger.V(2).Info("Starting controller manager")
	return mgr.Start(ctx)
}

func initFlags(flagset *flag.FlagSet, args []string) error {
	config.RegisterFlags(flagset)
	// Enable envvars as an alternative to args for flags in the 'config' package:
	if err := useEnvVarsToPopulateFlagValues(flagset); err != nil {
		return err
	}
	clientconfig.RegisterFlags(flagset)
	klog.InitFlags(flagset)
	pflag.CommandLine.Init("", pflag.ContinueOnError)
	pflag.CommandLine.AddGoFlagSet(flagset)
	if err := pflag.CommandLine.Parse(args); err != nil {
		return err
	}
	if err := viper.BindPFlags(pflag.CommandLine); err != nil {
		return fmt.Errorf("could not bind command line flags args=%+v: %w", args, err)
	}
	return nil
}

func useEnvVarsToPopulateFlagValues(flagset *flag.FlagSet) error {
	var errs []error
	flagset.VisitAll(func(f *flag.Flag) {
		envvarName := strings.ReplaceAll(strings.ToUpper(f.Name), "-", "_")
		if viper.GetEnvPrefix() != "" {
			envvarName = viper.GetEnvPrefix() + "_" + envvarName
		}
		if err := viper.BindEnv(f.Name, envvarName); err != nil {
			errs = append(errs, fmt.Errorf("could not bind environment variable %s to the config key %s: %w", envvarName, f.Name, err))
		}
		f.Usage += " Can also be set using the environment variable " + envvarName + "."
		if viper.IsSet(f.Name) {
			if err := f.Value.Set(viper.GetString(f.Name)); err != nil {
				errs = append(errs, fmt.Errorf("could not set value of flag %s to %s: %w", f.Name, viper.GetString(f.Name), err))
			}
		}
	})
	return errors.Join(errs...)
}
