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
import retrofit2.http.Query

@Serializable
data class Anime(
    val id: Int,
    val title: String,
    val coverUrl: String,
    val playUrls: String = "",
    val japaneseTitle: String = ""
)

data class Episode(val title: String, val url: String)

// ====================== API ======================
interface NetflixApi {
    @GET("api/netflix")
    suspend fun getList(
        @Query("page") page: Int = 1,
        @Query("pageSize") pageSize: Int = 30   // 和 Web 版保持一致
    ): List<Anime>
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
                    composable("detail/{animeId}") { backStack ->
                        val id = backStack.arguments?.getString("animeId")?.toInt() ?: 0
                        DetailScreen(id, api, imageBaseUrl, navController)
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
    var currentPage by remember { mutableStateOf(1) }
    var isLoading by remember { mutableStateOf(true) }
    var isLoadingMore by remember { mutableStateOf(false) }
    var hasMore by remember { mutableStateOf(true) }

    val scope = rememberCoroutineScope()

    // 加载分页
    suspend fun loadPage(page: Int, onResult: (List<Anime>, Boolean) -> Unit) {
        try {
            val newItems = withContext(Dispatchers.IO) {
                api.getList(page = page, pageSize = 30)
            }
            val hasMoreData = newItems.size >= 30
            onResult(newItems, hasMoreData)
        } catch (e: Exception) {
            Log.e("HomeScreen", "加载失败", e)
        }
    }

    // 过滤（本地搜索）
    val filteredList = remember(searchText, animeList) {
        if (searchText.isBlank()) animeList
        else animeList.filter { anime ->
            anime.title.contains(searchText, ignoreCase = true) ||
                    anime.japaneseTitle.contains(searchText, ignoreCase = true)
        }
    }

    // 初始加载第一页
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
            // ==================== 搜索框（保留你原来的清除按钮） ====================
            OutlinedTextField(
                value = searchText,
                onValueChange = { searchText = it },
                label = { Text("搜索动漫...") },
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp),
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                trailingIcon = {
                    if (searchText.isNotEmpty()) {
                        IconButton(onClick = {
                            searchText = ""
                            // 清空搜索后重新加载第一页
                            isLoading = true
                            currentPage = 1
                            scope.launch {
                                loadPage(1) { list, more ->
                                    animeList = list
                                    hasMore = more
                                    isLoading = false
                                }
                            }
                        }) {
                            Icon(
                                imageVector = Icons.Default.Clear,
                                contentDescription = "清除搜索"
                            )
                        }
                    }
                }
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
                            navController.navigate("detail/${anime.id}")
                        }
                    }

                    // ====================== Load More ======================
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
                                        CircularProgressIndicator(
                                            modifier = Modifier.size(20.dp),
                                            color = Color.White
                                        )
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

@Composable
fun AnimeCard(
    anime: Anime,
    imageBaseUrl: String,
    onClick: () -> Unit
) {
    val mainImage = imageBaseUrl + anime.coverUrl
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
                    // 1. 如果主图加载失败，自动换成默认封面
                    error = rememberAsyncImagePainter(defaultCover),
                    // 2. 在主图还没加载出来的时候，显示的占位图（可选）
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
fun DetailScreen(animeId: Int, api: NetflixApi, imageBaseUrl: String, navController: NavHostController) {
    var anime by remember { mutableStateOf<Anime?>(null) }
    var episodes by remember { mutableStateOf<List<Episode>>(emptyList()) }
    var currentEpisode by remember { mutableStateOf<Episode?>(null) }

    val context = LocalContext.current
    val player = remember { ExoPlayer.Builder(context).build() }

    LaunchedEffect(animeId) {
        val list = withContext(Dispatchers.IO) { api.getList() }
        anime = list.find { it.id == animeId }
        anime?.let {
            episodes = parsePlayUrls(it.playUrls)
            if (episodes.isNotEmpty()) {
                currentEpisode = episodes[0]
                playUrl(player, episodes[0].url)
            }
        }
    }

    DisposableEffect(Unit) { onDispose { player.release() } }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(anime?.title ?: "详情") },
                navigationIcon = { IconButton(onClick = { navController.popBackStack() }) { Text("←") } },
                colors = TopAppBarDefaults.topAppBarColors(Color(0xFF141414))
            )
        }
    ) { padding ->
        Column(Modifier.padding(padding)) {
            // 播放器
            Box(Modifier.fillMaxWidth().height(260.dp)) {
                AndroidView(factory = { PlayerView(it).apply { this.player = player } })
            }

            // 剧集列表
            LazyColumn(Modifier.padding(12.dp)) {
                itemsIndexed(episodes) { index, ep ->
                    ListItem(
                        headlineContent = { Text(ep.title) },
                        colors = ListItemDefaults.colors(
                            containerColor = if (ep == currentEpisode) Color(0xFF333333) else Color.Transparent
                        ),
                        modifier = Modifier.clickable {
                            currentEpisode = ep
                            playUrl(player, ep.url)
                        }
                    )
                }
            }
        }
    }
}

private fun parsePlayUrls(playUrls: String): List<Episode> {
    return playUrls.split("#").mapNotNull {
        val parts = it.split("$")
        if (parts.size == 2) Episode(parts[0], parts[1]) else null
    }
}

private fun playUrl(player: ExoPlayer, url: String) {
    val mediaItem = MediaItem.fromUri(url)
    player.setMediaItem(mediaItem)
    player.prepare()
    player.play()
}