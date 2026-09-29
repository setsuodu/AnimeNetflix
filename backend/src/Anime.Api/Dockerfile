# 1. 使用 .NET 10 SDK 进行编译
# build context = backend/（与 docker-compose.yml 同级）
FROM mcr.microsoft.com/dotnet/sdk:10.0-alpine AS build
WORKDIR /src

# 2. 复制项目文件并恢复依赖 (利用 Docker 缓存)
COPY ["src/Anime.Api/Anime.Api.csproj", "src/Anime.Api/"]
COPY ["src/Anime.Infrastructure/Anime.Infrastructure.csproj", "src/Anime.Infrastructure/"]
RUN dotnet restore "src/Anime.Api/Anime.Api.csproj"

# 3. 复制剩余源码并发布
COPY . .
WORKDIR "/src/src/Anime.Api"

# ★★★★★ 使用 GitHub Tag 作为版本 ★★★★★
ARG VERSION=1.0.0
RUN dotnet publish "Anime.Api.csproj" -c Release -o /app/publish \
    /p:Version=$VERSION \
    /p:AssemblyVersion=$VERSION \
    /p:FileVersion=$VERSION \
    /p:InformationalVersion=$VERSION

# 4. 生成运行镜像
FROM mcr.microsoft.com/dotnet/aspnet:10.0-alpine AS final

ARG VERSION=1.0.0
ARG BUILD_DATE

LABEL org.opencontainers.image.source="https://github.com/setsuodu/AnimeNetflix"
LABEL org.opencontainers.image.description="自宅动漫影院"
LABEL org.opencontainers.image.version="${VERSION}"
LABEL org.opencontainers.image.licenses="Apache-2.0"

WORKDIR /app
COPY --from=build /app/publish .

# seed.json（相对 build context = backend/）
COPY src/Anime.Api/seed.json ./

# .net10.0-alpine 瘦身过头报错 libgssapi_krb5
RUN apk add --no-cache krb5-libs

ENV ASPNETCORE_ENVIRONMENT=Production
ENV ASPNETCORE_URLS=http://+:8060
EXPOSE 8060

USER app
ENTRYPOINT ["dotnet", "Anime.Api.dll"]
