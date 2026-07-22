package uk.co.homebrain.hubitatmcpai;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.graphics.Color;
import android.os.Bundle;
import android.view.View;
import android.webkit.SslErrorHandler;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.TextView;

import java.net.URI;

public final class MainActivity extends Activity {
    private static final String DASHBOARD_URL = BuildConfig.DASHBOARD_URL;
    private WebView webView;
    private TextView errorView;

    @Override
    @SuppressLint("SetJavaScriptEnabled")
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().setStatusBarColor(Color.rgb(15, 15, 16));
        getWindow().setNavigationBarColor(Color.rgb(15, 15, 16));
        setContentView(R.layout.activity_main);

        webView = findViewById(R.id.webView);
        errorView = findViewById(R.id.errorView);

        webView.getSettings().setJavaScriptEnabled(true);
        webView.getSettings().setDomStorageEnabled(true);
        webView.getSettings().setAllowFileAccess(false);
        webView.getSettings().setAllowContentAccess(false);
        webView.getSettings().setMediaPlaybackRequiresUserGesture(false);
        webView.setWebViewClient(new LocalOnlyWebViewClient());

        if (savedInstanceState == null) {
            webView.loadUrl(DASHBOARD_URL);
        } else {
            webView.restoreState(savedInstanceState);
        }
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        webView.saveState(outState);
        super.onSaveInstanceState(outState);
    }

    @Override
    public void onBackPressed() {
        if (webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }

    private void showError(String message) {
        errorView.setText(message + "\n\nCheck that the phone is on your home Wi-Fi and Hubitat MCP AI is running at " + DASHBOARD_URL);
        errorView.setVisibility(View.VISIBLE);
        webView.setVisibility(View.GONE);
    }

    private boolean isAllowed(String candidate) {
        try {
            URI expected = URI.create(DASHBOARD_URL);
            URI actual = URI.create(candidate);
            return expected.getScheme().equalsIgnoreCase(actual.getScheme())
                    && expected.getHost().equalsIgnoreCase(actual.getHost())
                    && effectivePort(expected) == effectivePort(actual);
        } catch (RuntimeException exception) {
            return false;
        }
    }

    private int effectivePort(URI uri) {
        if (uri.getPort() >= 0) return uri.getPort();
        return "https".equalsIgnoreCase(uri.getScheme()) ? 443 : 80;
    }

    private final class LocalOnlyWebViewClient extends WebViewClient {
        @Override
        public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
            String url = request.getUrl().toString();
            if (isAllowed(url)) return false;
            showError("Blocked a link outside the configured HomeBrain dashboard.");
            return true;
        }

        @Override
        public void onPageFinished(WebView view, String url) {
            if (isAllowed(url)) {
                errorView.setVisibility(View.GONE);
                webView.setVisibility(View.VISIBLE);
            }
        }

        @Override
        public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
            if (request.isForMainFrame()) {
                showError("Could not connect to Hubitat MCP AI.");
            }
        }

        @Override
        public void onReceivedSslError(WebView view, SslErrorHandler handler, android.net.http.SslError error) {
            handler.cancel();
            showError("The dashboard returned an invalid HTTPS certificate.");
        }
    }
}
