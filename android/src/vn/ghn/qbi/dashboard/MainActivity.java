package vn.ghn.qbi.dashboard;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.SharedPreferences;
import android.text.InputType;
import android.widget.EditText;
import android.app.DownloadManager;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.Typeface;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.CookieManager;
import android.webkit.URLUtil;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

/**
 * App Android của dashboard GHN: mở thẳng dashboard trên Render trong WebView toàn màn hình.
 * Mọi tính năng, số liệu và bản cập nhật đều nằm ở dashboard, nên sửa dashboard là app tự có bản mới,
 * không cần cài lại app.
 */
public class MainActivity extends Activity {

    private static final int BLUE = Color.parseColor("#0077B6");
    private static final int ORANGE = Color.parseColor("#FF8C00");
    private static final int MUTED = Color.parseColor("#6C757D");
    private static final String RETRY = "ghnapp://retry";
    private static final String SET_URL = "ghnapp://seturl";

    private WebView web;
    private ProgressBar bar;
    private View splash;
    private TextView splashStatus;
    private String baseUrl;
    private String baseHost;
    private boolean pageError = false;
    private boolean splashHidden = false;
    private final Handler ui = new Handler(Looper.getMainLooper());

    // Lượt tải chờ cấp quyền lưu file (Android 9 trở xuống)
    private String pendingUrl, pendingDisposition, pendingMime;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        // Địa chỉ dashboard: ghi sẵn lúc build (build.sh <url>); nếu chưa ghi thì hỏi ở lần mở đầu tiên và nhớ lại.
        String baked = getString(R.string.base_url).trim();
        String saved = prefs().getString("url", null);
        setBase(isBaked(baked) ? baked : (saved != null ? saved : ""));

        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(Color.WHITE);

        web = new WebView(this);
        root.addView(web, new FrameLayout.LayoutParams(-1, -1));

        bar = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        bar.setMax(100);
        bar.setProgressTintList(ColorStateList.valueOf(ORANGE));
        bar.setVisibility(View.GONE);
        root.addView(bar, new FrameLayout.LayoutParams(-1, dp(4), Gravity.TOP));

        splash = buildSplash();
        root.addView(splash, new FrameLayout.LayoutParams(-1, -1));

        setContentView(root);
        setupWebView();

        if (baseUrl.isEmpty()) {
            askUrl();
        } else if (savedInstanceState != null && web.restoreState(savedInstanceState) != null) {
            hideSplash(0);
        } else {
            web.loadUrl(baseUrl);
        }
        // Render gói miễn phí "ngủ" khi lâu không ai mở: lần đầu có thể mất gần 1 phút để máy chủ khởi động.
        ui.postDelayed(() -> {
            if (!splashHidden) splashStatus.setText("Máy chủ đang khởi động, có thể mất tới 1 phút…");
        }, 12000);
    }

    private SharedPreferences prefs() {
        return getSharedPreferences("ghn_dashboard", MODE_PRIVATE);
    }

    private static boolean isBaked(String u) {
        return u.startsWith("http") && !u.contains("example.onrender.com");
    }

    private void setBase(String u) {
        u = u.trim();
        while (u.endsWith("/")) u = u.substring(0, u.length() - 1);
        baseUrl = u;
        baseHost = u.isEmpty() ? null : Uri.parse(u).getHost();
    }

    /** Hỏi địa chỉ dashboard (chỉ khi APK chưa được ghi sẵn địa chỉ lúc build). */
    private void askUrl() {
        final EditText in = new EditText(this);
        in.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        in.setHint("https://ten-app.onrender.com");
        if (!baseUrl.isEmpty()) in.setText(baseUrl);
        LinearLayout pad = new LinearLayout(this);
        pad.setPadding(dp(20), dp(8), dp(20), 0);
        pad.addView(in, new LinearLayout.LayoutParams(-1, -2));
        new AlertDialog.Builder(this)
                .setTitle("Địa chỉ dashboard")
                .setMessage("Nhập địa chỉ dashboard trên Render (chỉ cần nhập một lần).")
                .setView(pad)
                .setCancelable(false)
                .setPositiveButton("Mở dashboard", (d, w) -> {
                    String u = in.getText().toString().trim();
                    if (!u.startsWith("http")) u = "https://" + u;
                    if (Uri.parse(u).getHost() == null || !u.contains(".")) {
                        Toast.makeText(this, "Địa chỉ chưa đúng, hãy nhập lại", Toast.LENGTH_SHORT).show();
                        askUrl();
                        return;
                    }
                    setBase(u);
                    prefs().edit().putString("url", baseUrl).apply();
                    pageError = false;
                    splashHidden = false;
                    splash.setAlpha(1f);
                    splash.setVisibility(View.VISIBLE);
                    web.loadUrl(baseUrl);
                })
                .show();
    }

    private View buildSplash() {
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setGravity(Gravity.CENTER);
        box.setBackgroundColor(Color.WHITE);
        box.setPadding(dp(32), dp(32), dp(32), dp(32));

        ImageView logo = new ImageView(this);
        logo.setImageResource(R.drawable.splash_logo);
        box.addView(logo, new LinearLayout.LayoutParams(dp(120), dp(120)));

        TextView title = new TextView(this);
        title.setText("TRUNG TÂM VẬN HÀNH - KINH DOANH");
        title.setTextColor(BLUE);
        title.setTextSize(18);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        title.setGravity(Gravity.CENTER);
        title.setPadding(0, dp(20), 0, dp(4));
        box.addView(title);

        TextView slogan = new TextView(this);
        slogan.setText("KỶ LUẬT LÀ SỨC MẠNH");
        slogan.setTextColor(ORANGE);
        slogan.setTextSize(13);
        slogan.setTypeface(Typeface.DEFAULT_BOLD);
        slogan.setLetterSpacing(0.12f);
        slogan.setGravity(Gravity.CENTER);
        box.addView(slogan);

        ProgressBar spin = new ProgressBar(this);
        spin.setIndeterminateTintList(ColorStateList.valueOf(ORANGE));
        LinearLayout.LayoutParams sp = new LinearLayout.LayoutParams(dp(36), dp(36));
        sp.topMargin = dp(32);
        box.addView(spin, sp);

        splashStatus = new TextView(this);
        splashStatus.setText("Đang tải dữ liệu…");
        splashStatus.setTextColor(MUTED);
        splashStatus.setTextSize(13);
        splashStatus.setGravity(Gravity.CENTER);
        splashStatus.setPadding(0, dp(12), 0, 0);
        box.addView(splashStatus);
        return box;
    }

    private void setupWebView() {
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setLoadWithOverviewMode(true);
        s.setUseWideViewPort(true);
        s.setTextZoom(100);
        s.setSupportZoom(false);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setUserAgentString(s.getUserAgentString() + " GHNDashboardApp/1.0");

        CookieManager cm = CookieManager.getInstance();
        cm.setAcceptCookie(true);
        cm.setAcceptThirdPartyCookies(web, true);   // giữ đăng nhập (cookie ghn_auth) giữa các lần mở app

        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest req) {
                return handleUrl(req.getUrl());
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                CookieManager.getInstance().flush();
                // Streamlit vẽ giao diện sau khi trang tải xong: chờ thêm chút cho khỏi thấy màn trắng.
                if (!pageError && url != null && url.startsWith("http")) hideSplash(1500);
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest req, WebResourceError err) {
                if (req.isForMainFrame()) showOffline();
            }
        });

        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onProgressChanged(WebView view, int p) {
                bar.setProgress(p);
                bar.setVisibility(p < 100 && splashHidden ? View.VISIBLE : View.GONE);
            }
        });

        // Nút "Tải ảnh / tải file" trên dashboard: lưu vào thư mục Download của điện thoại.
        web.setDownloadListener((url, ua, disposition, mime, len) -> download(url, disposition, mime));
    }

    /** Link cùng máy chủ dashboard mở trong app; link khác (Google Sheet, Telegram, Zalo...) mở bằng app ngoài. */
    private boolean handleUrl(Uri u) {
        String url = u.toString();
        if (url.equals(RETRY)) {
            pageError = false;
            web.loadUrl(baseUrl);
            return true;
        }
        if (url.equals(SET_URL)) {
            askUrl();
            return true;
        }
        String scheme = u.getScheme() == null ? "" : u.getScheme();
        if ((scheme.equals("https") || scheme.equals("http")) && baseHost != null && baseHost.equalsIgnoreCase(u.getHost())) {
            return false;
        }
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, u));
        } catch (ActivityNotFoundException e) {
            Toast.makeText(this, "Không có ứng dụng để mở liên kết này", Toast.LENGTH_SHORT).show();
        }
        return true;
    }

    private void hideSplash(long delay) {
        ui.postDelayed(() -> {
            if (splashHidden) return;
            splashHidden = true;
            splash.animate().alpha(0f).setDuration(250).withEndAction(() -> splash.setVisibility(View.GONE));
        }, delay);
    }

    private void showOffline() {
        pageError = true;
        String html = "<html><head><meta name='viewport' content='width=device-width,initial-scale=1'>"
                + "<style>body{font-family:sans-serif;text-align:center;padding:60px 24px;color:#212529}"
                + "h2{color:#0077B6}a{display:inline-block;margin-top:24px;padding:14px 28px;background:#FF8C00;"
                + "color:#fff;border-radius:8px;text-decoration:none;font-weight:bold}</style></head><body>"
                + "<h2>Không kết nối được dashboard</h2>"
                + "<p>Kiểm tra kết nối mạng (Wi-Fi / 4G) rồi bấm thử lại.<br>"
                + "Nếu máy chủ vừa khởi động, chờ khoảng 1 phút.</p>"
                + "<a href='" + RETRY + "'>THỬ LẠI</a>"
                + (isBaked(getString(R.string.base_url).trim()) ? "" :
                   "<p style='margin-top:28px'><a href='" + SET_URL + "' style='background:#0077B6'>ĐỔI ĐỊA CHỈ</a></p>"
                   + "<p style='color:#6C757D;font-size:13px'>Đang mở: " + baseUrl + "</p>")
                + "</body></html>";
        web.loadDataWithBaseURL(null, html, "text/html", "utf-8", null);
        hideSplash(0);
    }

    private void download(String url, String disposition, String mime) {
        if (url == null || !(url.startsWith("http://") || url.startsWith("https://"))) {
            Toast.makeText(this, "Không tải được file này trong app, hãy mở dashboard bằng trình duyệt.",
                    Toast.LENGTH_LONG).show();
            return;
        }
        if (Build.VERSION.SDK_INT < 29
                && checkSelfPermission(Manifest.permission.WRITE_EXTERNAL_STORAGE) != PackageManager.PERMISSION_GRANTED) {
            pendingUrl = url;
            pendingDisposition = disposition;
            pendingMime = mime;
            requestPermissions(new String[]{Manifest.permission.WRITE_EXTERNAL_STORAGE}, 7);
            return;
        }
        try {
            String name = URLUtil.guessFileName(url, disposition, mime);
            DownloadManager.Request r = new DownloadManager.Request(Uri.parse(url));
            r.setMimeType(mime);
            String cookie = CookieManager.getInstance().getCookie(url);
            if (cookie != null) r.addRequestHeader("Cookie", cookie);
            r.setTitle(name);
            r.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
            r.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, name);
            ((DownloadManager) getSystemService(DOWNLOAD_SERVICE)).enqueue(r);
            Toast.makeText(this, "Đang tải " + name + " vào thư mục Download", Toast.LENGTH_SHORT).show();
        } catch (Exception e) {
            Toast.makeText(this, "Tải file không thành công", Toast.LENGTH_SHORT).show();
        }
    }

    @Override
    public void onRequestPermissionsResult(int code, String[] perms, int[] res) {
        super.onRequestPermissionsResult(code, perms, res);
        if (code == 7 && res.length > 0 && res[0] == PackageManager.PERMISSION_GRANTED && pendingUrl != null) {
            download(pendingUrl, pendingDisposition, pendingMime);
        }
        pendingUrl = null;
    }

    @Override
    public void onBackPressed() {
        if (web.canGoBack()) {
            web.goBack();
        } else {
            super.onBackPressed();
        }
    }

    @Override
    protected void onSaveInstanceState(Bundle out) {
        super.onSaveInstanceState(out);
        web.saveState(out);
    }

    @Override
    protected void onPause() {
        super.onPause();
        web.onPause();
        CookieManager.getInstance().flush();
    }

    @Override
    protected void onResume() {
        super.onResume();
        web.onResume();
    }

    @Override
    protected void onDestroy() {
        ui.removeCallbacksAndMessages(null);
        if (web != null) {
            ((ViewGroup) web.getParent()).removeView(web);
            web.destroy();
        }
        super.onDestroy();
    }

    private int dp(int v) {
        return Math.round(v * getResources().getDisplayMetrics().density);
    }
}
