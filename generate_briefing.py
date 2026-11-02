import os
import sys
import yaml
import shutil
import logging
from pathlib import Path
from datetime import datetime, timezone
from sarvamai import SarvamAI

from sources import RSSSource, BlueskySource, TelegramSource, TwitterSource, NewsItem
from core import CacheManager, NewsDeduplicator, NewsSummarizer, BriefingTTS

# Ensure UTF-8 output on Windows consoles
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("DailyBriefing")


def load_env():
    """Load .env file into os.environ if present."""
    env_file = Path(__file__).resolve().parent / ".env"
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())


def load_config(config_path: str = "sources.yaml") -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_pipeline():
    load_env()
    api_key = os.environ.get("SARVAM_API_KEY")
    if not api_key:
        logger.error("SARVAM_API_KEY not found in environment or .env file.")
        sys.exit(1)

    config = load_config()
    briefing_cfg = config.get("briefing", {})
    sources_cfg = config.get("sources", {})

    top_n = briefing_cfg.get("top_stories", 8)
    hours_window = briefing_cfg.get("hours_window", 24)
    lang_code = briefing_cfg.get("language_code", "en-IN")
    speaker = briefing_cfg.get("tts_speaker", "shreya")
    tts_model = briefing_cfg.get("tts_model", "bulbul:v3")
    llm_model = briefing_cfg.get("llm_model", "sarvam-105b-conversations")

    cache = CacheManager()
    client = SarvamAI(api_subscription_key=api_key)

    all_items: list[NewsItem] = []

    # 1. Fetch RSS
    rss_cfg = sources_cfg.get("rss", {})
    if rss_cfg.get("enabled", True):
        logger.info("--- Ingesting RSS Feeds ---")
        rss_source = RSSSource(rss_cfg.get("feeds", []))
        all_items.extend(rss_source.fetch_items(hours_window=hours_window))

    # 2. Fetch Bluesky
    bsky_cfg = sources_cfg.get("bluesky", {})
    if bsky_cfg.get("enabled", False):
        logger.info("--- Ingesting Bluesky Accounts ---")
        bsky_source = BlueskySource(bsky_cfg.get("accounts", []))
        all_items.extend(bsky_source.fetch_items(hours_window=hours_window))

    # 3. Fetch Telegram
    tg_cfg = sources_cfg.get("telegram", {})
    if tg_cfg.get("enabled", False):
        logger.info("--- Ingesting Telegram Channels ---")
        tg_source = TelegramSource(tg_cfg.get("channels", []))
        all_items.extend(tg_source.fetch_items(hours_window=hours_window))

    # 4. Fetch Twitter (Optional)
    tw_cfg = sources_cfg.get("twitter", {})
    if tw_cfg.get("enabled", False):
        logger.info("--- Ingesting X/Twitter Accounts ---")
        tw_source = TwitterSource(tw_cfg.get("accounts", []), enabled=True)
        all_items.extend(tw_source.fetch_items(hours_window=hours_window))

    logger.info(f"Total raw news items collected: {len(all_items)}")
    if not all_items:
        logger.warning("No news items retrieved from any source. Check internet connection and feeds.")
        return

    # 5. Deduplicate, group & rank
    logger.info("--- Deduplicating & Ranking Stories ---")
    dedup = NewsDeduplicator()
    grouped_stories = dedup.group_and_rank(all_items, max_stories=top_n)
    logger.info(f"Selected top {len(grouped_stories)} distinct stories.")

    # 6. Summarize with Sarvam LLM
    logger.info("--- Summarizing with Sarvam LLM ---")
    summarizer = NewsSummarizer(client=client, model=llm_model, cache=cache)
    summarized_stories = summarizer.summarize_all(grouped_stories)

    # 7. Synthesize Audio Briefing
    logger.info("--- Generating Audio with Sarvam TTS (Bulbul) ---")
    tts = BriefingTTS(
        client=client,
        language_code=lang_code,
        speaker=speaker,
        model=tts_model,
        cache=cache
    )

    now = datetime.now()
    date_readable = now.strftime("%A, %B %d")
    date_code = now.strftime("%Y%m%d")

    spoken_scripts = [s.spoken_summary for s in summarized_stories]
    master_audio = tts.generate_full_briefing_audio(spoken_scripts, date_str=date_readable)

    # 8. Save output
    briefing_payload = {
        "date": date_readable,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_stories": len(summarized_stories),
        "stories": [
            {
                "id": s.id,
                "title": s.title,
                "spoken_summary": s.spoken_summary,
                "written_summary": s.written_summary,
                "sources": [
                    {
                        "name": src.name,
                        "platform": src.platform,
                        "url": src.url,
                        "is_social": src.is_social
                    }
                    for src in s.sources
                ]
            }
            for s in summarized_stories
        ]
    }

    paths = cache.save_briefing_result(date_code, briefing_payload, master_audio)

    # Maintain latest.mp3 and latest.json pointers
    out_dir = Path("data/output")
    shutil.copyfile(paths["audio_path"], out_dir / "latest.mp3")
    shutil.copyfile(paths["json_path"], out_dir / "latest.json")

    logger.info("==================================================")
    logger.info("DAILY NEWS BRIEFING COMPLETED SUCCESSFULLY!")
    logger.info(f"Audio file: {paths['audio_path']} ({len(master_audio)} bytes)")
    logger.info(f"Transcript JSON: {paths['json_path']}")
    logger.info("==================================================")


if __name__ == "__main__":
    run_pipeline()
