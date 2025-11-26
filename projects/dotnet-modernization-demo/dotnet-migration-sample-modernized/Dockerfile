# Use the .NET 8 SDK image for building the application
FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /app

# Copy csproj and restore as distinct layers
COPY *.sln .
COPY ContosoUniversity/*.csproj ./ContosoUniversity/
RUN dotnet restore

# Copy everything else and build
COPY . .
WORKDIR /app/ContosoUniversity
RUN dotnet publish -c Release -o out

# Use the .NET 8 ASP.NET runtime image for the final application
FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS runtime
WORKDIR /app
COPY --from=build /app/ContosoUniversity/out ./
ENTRYPOINT ["dotnet", "ContosoUniversity.dll"]
