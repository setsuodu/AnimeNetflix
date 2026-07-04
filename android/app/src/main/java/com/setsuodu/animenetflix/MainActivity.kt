package com.setsuodu.animenetflix

import android.os.Bundle
import android.util.Log
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.grid.GridItemSpan
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Clear
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.media3.common.MediaItem
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.ui.PlayerView
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import coil.compose.AsyncImage
import coil.compose.rememberAsyncImagePainter
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory
import retrofit2.http.GET
import retrofit2.http.Path
import retrofit2.http.Query

@Serializable
data class Anime(
    val sourceFingerprint: String,     // 新主键
    val title: String,
    val japaneseTitle: String = "",
    val englishTitle: String = "",
    val coverUrl: String = "",
    val playUrls: String = "",         // 主线路（金鹰）
    val backupUrls: String = "",       // 备用线路（红牛）
    val year: Int = 0,
    val area: String = "",
    val category: String = "",
    val episodes: String = ""
)

data class Episode(val title: String, val url: String)

interface NetflixApi {
    @GET("api/netflix")
    suspend fun getList(
        @Query("page") page: Int = 1,
        @Query("pageSize") pageSize: Int = 30,
        @Query("search") search: String? = null,
        @Query("year") year: Int? = null,
        @Query("area") area: String? = null,
        @Query("category") category: String? = null
    ): List<Anime>

    // ✅ 改成 fingerprint
    @GET("api/netflix/{fingerprint}")
    suspend fun getDetail(@Path("fingerprint") fingerprint: String): Anime
}

// ====================== MainActivity ======================
class MainActivity : ComponentActivity() {

    private val apiBaseUrl = "http://192.168.1.198:8060/"      // API
    private val imageBaseUrl = "http://192.168.1.198:8061/"   // covers 图片

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val retrofit = Retrofit.Builder()
            .baseUrl(apiBaseUrl)
            .client(OkHttpClient.Builder()
                .addInterceptor(HttpLoggingInterceptor { Log.d("HTTP", it) }.setLevel(HttpLoggingInterceptor.Level.BODY))
                .build())
            .addConverterFactory(Json { ignoreUnknownKeys = true }.asConverterFactory("application/json".toMediaType()))
            .build()

        val api = retrofit.create(NetflixApi::class.java)

        setContent {
            MaterialTheme(colorScheme = darkColorScheme()) {
                val navController = rememberNavController()
                NavHost(navController = navController, startDestination = "home") {
                    composable("home") {
                        HomeScreen(api, imageBaseUrl, navController)
                    }
                    composable("detail/{fingerprint}") { backStack ->
                        val fingerprint = backStack.arguments?.getString("fingerprint") ?: ""
                        DetailScreen(fingerprint, api, imageBaseUrl, navController)
                    }
                }
            }
        }
    }
}

// ====================== 首页 ======================
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(api: NetflixApi, imageBaseUrl: String, navController: NavHostController) {
    var animeList by remember { mutableStateOf<List<Anime>>(emptyList()) }
    var searchText by remember { mutableStateOf("") }
    // 与 index.html 的 filter-area 下拉框保持一致：全部地区/日本/中国/美国
    var selectedArea by remember { mutableStateOf("全部地区") }
    var currentPage by remember { mutableStateOf(1) }
    var isLoading by remember { mutableStateOf(true) }
    var isLoadingMore by remember { mutableStateOf(false) }
    var hasMore by remember { mutableStateOf(true) }

    val scope = rememberCoroutineScope()

    suspend fun loadPage(page: Int, onResult: (List<Anime>, Boolean) -> Unit) {
        try {
            val newItems = withContext(Dispatchers.IO) {
                api.getList(
                    page = page,
                    pageSize = 30,
                    search = if (searchText.isBlank()) null else searchText,
                    area = if (selectedArea == "全部地区") null else selectedArea
                )
            }
            val hasMoreData = newItems.size >= 30
            onResult(newItems, hasMoreData)
        } catch (e: Exception) {
            Log.e("HomeScreen", "加载失败", e)
        }
    }

    val filteredList = animeList // 现在服务端支持 search，可直接用

    LaunchedEffect(Unit) {
        loadPage(1) { list, more ->
            animeList = list
            hasMore = more
            isLoading = false
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("AnimeNetflix") },
                colors = TopAppBarDefaults.topAppBarColors(Color(0xFF141414))
            )
        }
    ) { padding ->
        Column(Modifier.padding(padding)) {
            OutlinedTextField(
                value = searchText,
                onValueChange = {
                    searchText = it
                    currentPage = 1
                    isLoading = true
                    scope.launch {
                        loadPage(1) { list, more ->
                            animeList = list
                            hasMore = more
                            isLoading = false
                        }
                    }
                },
                label = { Text("搜索动漫...") },
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp),
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                trailingIcon = {
                    if (searchText.isNotEmpty()) {
                        IconButton(onClick = {
                            searchText = ""
                            currentPage = 1
                            isLoading = true
                            scope.launch {
                                loadPage(1) { list, more ->
                                    animeList = list
                                    hasMore = more
                                    isLoading = false
                                }
                            }
                        }) {
                            Icon(Icons.Default.Clear, "清除")
                        }
                    }
                }
            )

            // 筛选栏：目前对齐 index.html 已完善的地区筛选（年份/类型待后端提供 /api/netflix/filters 后再补齐）
            AreaFilterDropdown(
                selectedArea = selectedArea,
                onAreaSelected = { area ->
                    selectedArea = area
                    currentPage = 1
                    isLoading = true
                    scope.launch {
                        loadPage(1) { list, more ->
                            animeList = list
                            hasMore = more
                            isLoading = false
                        }
                    }
                },
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 4.dp)
            )

            if (isLoading) {
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator()
                }
            } else {
                LazyVerticalGrid(
                    columns = GridCells.Fixed(3),
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(8.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    items(filteredList) { anime ->
                        AnimeCard(anime, imageBaseUrl) {
                            navController.navigate("detail/${anime.sourceFingerprint}")
                        }
                    }

                    if (hasMore && searchText.isBlank()) {
                        item(span = { GridItemSpan(3) }) {
                            Box(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(24.dp),
                                contentAlignment = Alignment.Center
                            ) {
                                Button(
                                    onClick = {
                                        isLoadingMore = true
                                        currentPage++
                                        scope.launch {
                                            loadPage(currentPage) { newItems, more ->
                                                animeList = animeList + newItems
                                                hasMore = more
                                                isLoadingMore = false
                                            }
                                        }
                                    },
                                    enabled = !isLoadingMore,
                                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFF679A))
                                ) {
                                    if (isLoadingMore) {
                                        CircularProgressIndicator(modifier = Modifier.size(20.dp), color = Color.White)
                                    } else {
                                        Text("查看更多")
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

// 地区筛选下拉框：与 index.html 里写死的 filter-area 选项保持一致
// （日本/中国/美国 —— 对应 NetflixController.GetList 的 area 精确匹配字段）
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AreaFilterDropdown(
    selectedArea: String,
    onAreaSelected: (String) -> Unit,
    modifier: Modifier = Modifier
) {
    var expanded by remember { mutableStateOf(false) }
    val areas = listOf("全部地区", "日本", "中国", "美国")

    ExposedDropdownMenuBox(
        expanded = expanded,
        onExpandedChange = { expanded = it },
        modifier = modifier
    ) {
        OutlinedTextField(
            value = selectedArea,
            onValueChange = {},
            readOnly = true,
            label = { Text("地区") },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded) },
            modifier = Modifier
                .menuAnchor()
                .fillMaxWidth()
        )
        ExposedDropdownMenu(
            expanded = expanded,
            onDismissRequest = { expanded = false }
        ) {
            areas.forEach { area ->
                DropdownMenuItem(
                    text = { Text(area) },
                    onClick = {
                        onAreaSelected(area)
                        expanded = false
                    }
                )
            }
        }
    }
}

@Composable
fun AnimeCard(anime: Anime, imageBaseUrl: String, onClick: () -> Unit) {
    val mainImage = imageBaseUrl + anime.coverUrl.ifEmpty { "/images/default_cover.jpg" }
    val defaultCover = "http://192.168.1.198:8060/images/default_cover.jpg"

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .height(220.dp)
            .clickable { onClick() },
        colors = CardDefaults.cardColors(containerColor = Color(0xFF1F1F1F))
    ) {
        Column {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(170.dp)
                    .background(Color(0xFF2A2A2A))
            ) {
                AsyncImage(
                    model = mainImage,
                    contentDescription = anime.title,
                    modifier = Modifier.fillMaxSize(),
                    contentScale = ContentScale.Crop,
                    error = rememberAsyncImagePainter(defaultCover),
                    placeholder = rememberAsyncImagePainter(defaultCover)
                )
            }

            Text(
                text = anime.title,
                modifier = Modifier.padding(8.dp).fillMaxWidth(),
                style = MaterialTheme.typography.bodyMedium,
                maxLines = 2,
                color = Color.White
            )
        }
    }
}

// ====================== 详情页 + 播放器 ======================
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DetailScreen(
    fingerprint: String,           // ← 改成 fingerprint
    api: NetflixApi,
    imageBaseUrl: String,
    navController: NavHostController
) {
    var anime by remember { mutableStateOf<Anime?>(null) }
    var episodes by remember { mutableStateOf<List<Episode>>(emptyList()) }
    var currentSource by remember { mutableStateOf(1) } // 1=主线路(PlayUrls), 2=备用线路(BackupUrls)
    var currentEpisode by remember { mutableStateOf<Episode?>(null) }

    val context = LocalContext.current
    val player = remember { ExoPlayer.Builder(context).build() }

    // 加载详情
    LaunchedEffect(fingerprint) {
        try {
            val detail = withContext(Dispatchers.IO) {
                api.getDetail(fingerprint)
            }
            anime = detail

            // 默认加载主线路
            episodes = parsePlayUrls(detail.playUrls)
            if (episodes.isNotEmpty()) {
                currentEpisode = episodes[0]
                playUrl(player, episodes[0].url)
            }
        } catch (e: Exception) {
            Log.e("DetailScreen", "加载详情失败", e)
        }
    }

    DisposableEffect(Unit) {
        onDispose { player.release() }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(anime?.title ?: "加载中...") },
                navigationIcon = {
                    IconButton(onClick = { navController.popBackStack() }) {
                        Text("←", style = MaterialTheme.typography.titleLarge)
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(Color(0xFF141414))
            )
        }
    ) { padding ->
        Column(Modifier.padding(padding)) {
            // 播放器区域
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(260.dp)
                    .background(Color.Black)
            ) {
                AndroidView(
                    factory = { ctx ->
                        PlayerView(ctx).apply {
                            this.player = player
                            useController = true
                        }
                    }
                )
            }

            // 动漫信息
            anime?.let { a ->
                Column(Modifier.padding(16.dp)) {
                    // 副标题（日文 / 英文）
                    if (a.japaneseTitle.isNotBlank() || a.englishTitle.isNotBlank()) {
                        Text(
                            text = listOf(a.japaneseTitle, a.englishTitle).filter { it.isNotBlank() }.joinToString(" / "),
                            color = Color.Gray,
                            style = MaterialTheme.typography.bodyMedium
                        )
                    }

                    Spacer(Modifier.height(8.dp))

                    // 元信息标签
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        if (a.year > 0) MetaTag("${a.year}年")
                        if (a.area.isNotBlank()) MetaTag(a.area)
                        if (a.category.isNotBlank()) MetaTag(a.category)
                        if (a.episodes.isNotBlank()) MetaTag(a.episodes, highlight = true)
                    }
                }
            }

            // 线路切换
            Row(
                Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                SourceButton("主线路", currentSource == 1) {
                    currentSource = 1
                    anime?.let { episodes = parsePlayUrls(it.playUrls) }
                }
                SourceButton("备用线路", currentSource == 2) {
                    currentSource = 2
                    anime?.let { episodes = parsePlayUrls(it.backupUrls) }
                }
            }

            // 剧集列表
            Text(
                text = "剧集列表 (${episodes.size}集)",
                modifier = Modifier.padding(start = 16.dp, bottom = 8.dp),
                style = MaterialTheme.typography.titleSmall
            )

            LazyColumn(
                modifier = Modifier
                    .weight(1f)
                    .padding(horizontal = 12.dp)
            ) {
                itemsIndexed(episodes) { _, ep ->
                    ListItem(
                        headlineContent = { Text(ep.title) },
                        colors = ListItemDefaults.colors(
                            containerColor = if (ep == currentEpisode) Color(0xFF2A2A2A) else Color.Transparent
                        ),
                        modifier = Modifier
                            .padding(vertical = 2.dp)
                            .clickable {
                                currentEpisode = ep
                                playUrl(player, ep.url)
                            }
                    )
                }
            }
        }
    }
}

@Composable
fun MetaTag(text: String, highlight: Boolean = false) {
    Text(
        text = text,
        modifier = Modifier
            .background(
                color = if (highlight) Color(0xFF4A1F2A) else Color(0xFF2A2A2A),
                shape = MaterialTheme.shapes.small
            )
            .padding(horizontal = 10.dp, vertical = 4.dp),
        color = if (highlight) Color(0xFFFF679A) else Color.LightGray,
        style = MaterialTheme.typography.bodySmall
    )
}

@Composable
fun SourceButton(text: String, isActive: Boolean, onClick: () -> Unit) {
    Button(
        onClick = onClick,
        colors = ButtonDefaults.buttonColors(
            containerColor = if (isActive) Color(0xFFE50914) else Color(0xFF333333)
        )
    ) {
        Text(text)
    }
}

// ====================== 辅助函数 ======================
private fun parsePlayUrls(playUrls: String): List<Episode> {
    if (playUrls.isBlank()) return emptyList()
    return playUrls.split("#").mapNotNull { line ->
        val parts = line.split("$")
        if (parts.size >= 2) Episode(parts[0].trim(), parts[1].trim()) else null
    }
}

private fun playUrl(player: ExoPlayer, url: String) {
    try {
        val mediaItem = MediaItem.fromUri(url)
        player.setMediaItem(mediaItem)
        player.prepare()
        player.play()
    } catch (e: Exception) {
        Log.e("Player", "播放失败: $url", e)
    }
}