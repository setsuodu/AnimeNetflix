# 1. 使用 .NET 10 SDK 进行编译
FROM mcr.microsoft.com/dotnet/sdk:10.0-alpine AS build
WORKDIR /src

# 2. 复制项目文件并恢复依赖 (利用 Docker 缓存)
COPY ["Anime.Api/Anime.Api.csproj", "Anime.Api/"]
COPY ["Anime.Infrastructure/Anime.Infrastructure.csproj", "Anime.Infrastructure/"]
RUN dotnet restore "Anime.Api/Anime.Api.csproj"

# 3. 复制剩余源码并发布
COPY . .
WORKDIR "/src/Anime.Api"

# ★★★★★ 使用 GitHub Tag 作为版本 ★★★★★
ARG VERSION=1.0.0
RUN dotnet publish "Anime.Api.csproj" -c Release -o /app/publish \
    /p:Version=$VERSION \
    /p:AssemblyVersion=$VERSION \
    /p:FileVersion=$VERSION \
    /p:InformationalVersion=$VERSION

RUN dotnet publish "Anime.Api.csproj" -c Release -o /app/publish

# 4. 生成运行镜像
FROM mcr.microsoft.com/dotnet/aspnet:10.0-alpine AS final

ARG VERSION=1.0.0          # ← 新增这行，默认值
ARG BUILD_DATE

# 设置标签
LABEL org.opencontainers.image.source="https://github.com/setsuodu/AnimeNetflix"
LABEL org.opencontainers.image.description="自宅动漫影院"
LABEL org.opencontainers.image.version="${VERSION}"
LABEL org.opencontainers.image.licenses="Apache-2.0"

WORKDIR /app
COPY --from=build /app/publish .

# ★★★★★★★★ 重点：复制 seed.json ★★★★★★★★
COPY Anime.Api/seed.json ./

# .net10.0-alpine 瘦身过头报错
# Cannot load library libgssapi_krb5.so.2 
# Error: Error loading shared library libgssapi_krb5.so.2: No such file or directory
RUN apk add --no-cache krb5-libs

# 5. 设置环境变量和暴露端口
ENV ASPNETCORE_ENVIRONMENT=Production
# ← 这行最强力，优先级最高
ENV ASPNETCORE_URLS=http://+:8060
# 也可以，两行选一个就行
#ENV ASPNETCORE_HTTP_PORTS=8060
EXPOSE 8060

USER app
ENTRYPOINT ["dotnet", "Anime.Api.dll"]