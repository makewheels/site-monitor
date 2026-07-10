package com.makewheels.aimonitor;

import java.net.URI;

final class DisplayFormatter {
    private DisplayFormatter() {
    }

    static String cleanMarkdown(String value) {
        if (value == null || value.trim().isEmpty()) {
            return "";
        }
        return value
                .replaceAll("\\[([^\\]]+)]\\((https?://[^)]+)\\)", "$1\n$2")
                .replaceAll("(?m)^#{1,6}\\s*", "")
                .replace("**", "")
                .replace("`", "")
                .replaceAll("(?m)^\\s*[-*]\\s+", "• ")
                .replaceAll("(?m)^\\s*---+\\s*$", "")
                .replaceAll("\\n{3,}", "\n\n")
                .trim();
    }

    static boolean isHttpUrl(String value) {
        if (value == null) {
            return false;
        }
        String lowered = value.toLowerCase();
        return lowered.startsWith("https://") || lowered.startsWith("http://");
    }

    static boolean releaseAvailable(int latestVersionCode, int installedVersionCode) {
        return latestVersionCode > installedVersionCode;
    }

    static String hostLabel(String value) {
        try {
            URI uri = URI.create(value);
            return uri.getHost() == null ? value : uri.getHost();
        } catch (Exception ignored) {
            return value;
        }
    }
}
