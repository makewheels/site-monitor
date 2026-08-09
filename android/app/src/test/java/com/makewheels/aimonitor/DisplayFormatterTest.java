package com.makewheels.aimonitor;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class DisplayFormatterTest {
    @Test
    public void cleanMarkdownPreservesVisibleUrl() {
        String output = DisplayFormatter.cleanMarkdown(
                "## OpenAI News\n- [New model](https://openai.com/new-model)"
        );

        assertEquals("OpenAI News\n• New model\nhttps://openai.com/new-model", output);
    }

    @Test
    public void releaseCheckUsesVersionCode() {
        assertTrue(DisplayFormatter.releaseAvailable(3, 2));
        assertFalse(DisplayFormatter.releaseAvailable(2, 2));
    }

    @Test
    public void hostLabelHidesPathAndCredentials() {
        assertEquals("monitor.example.com", DisplayFormatter.hostLabel("https://monitor.example.com/api"));
    }

    @Test
    public void projectIntroTakesPriorityOverSourceUrl() {
        assertEquals(
                "https://monitor.example.com/projects/owner/repo",
                DisplayFormatter.primaryContentUrl(
                        "https://monitor.example.com/projects/owner/repo",
                        "https://github.com/owner/repo"
                )
        );
        assertEquals(
                "https://github.com/owner/repo",
                DisplayFormatter.primaryContentUrl("", "https://github.com/owner/repo")
        );
    }
}
