# Java Commons

This folder contains reusable Java components:

* `utils`
   Utility functions, e.g. handling Proto and Json.
* `spring-boot-auth`
   Spring Bean to extract Google Access token from
   Request header and allow inspecting approve scopes and
   principal email address.
* `objectify-testing`
   JUnit5 test extensions for unit-testing `Objectify` and `Datastore`
   operations.
* `testing`
   Utilities and extensions for helping with writing better tests.

## Using common components

1. Add to your `settings.gradle`

   ```groovy
   includeBuild("path/to/common/java-common")
   ```

2. Use appropriate module in your `build.gradle`:
   Example to use utils and testing module:

   ```groovy
   implementation "com.google.cloud.solutions.satools.common:utils"
   testImplementation "com.google.cloud.solutions.satools.common:testing"
   ```
