export interface AllQuestsResponse {
	/**
	 * The current quests for the user
	 */
	quests: Quest[];
	/**
	 * The quests that the user cannot participate in
	 */
	excluded_quests: Partial<Quest>[];
	/**
	 * When the user can enroll in quests again
	 */
	quest_enrollment_blocked_until: string | null;
}

export type Snowflake = string;

export interface Quest {
	/**
	 * The ID of the quest
	 */
	id: Snowflake;
	/**
	 * The configuration and metadata for the quest
	 */
	config: QuestConfig;
	/**
	 * The user's quest progress, if it has been accepted
	 */
	user_status: QuestUserStatus | null;
	/**
	 * The content areas where the quest can be shown
	 * @deprecated
	 */
	targeted_content: number;
	/**
	 * Whether the quest is unreleased and in preview for Discord employees
	 */
	preview: boolean;
	traffic_metadata_raw?: string;
	traffic_metadata_sealed?: string;
}

export interface QuestConfig {
	id: Snowflake;
	config_version: number;
	starts_at: string;
	expires_at: string;
	features: number;
	application: QuestApplication;
	assets: QuestAssets;
	colors: QuestGradient;
	messages: QuestMessages;
	rewards_config: QuestRewardsConfig;
	video_metadata?: QuestVideoMetadata;
	cosponsor_metadata?: QuestCosponsorMetadata;
	task_config_v2: {
		tasks: Record<
			QuestTaskConfigType,
			{ type: QuestTaskConfigType; target: number }
		>;
	};
}

export interface QuestUserStatus {
	user_id: Snowflake;
	quest_id?: Snowflake;
	enrolled_at: string | null;
	completed_at: string | null;
	claimed_at: string | null;
	claimed_tier?: number | null;
	last_stream_heartbeat_at?: string | null;
	stream_progress_seconds?: string;
	dismissed_quest_content?: number;
	progress: Record<string, QuestTaskProgress>;
}

export interface QuestTaskProgress {
	event_name: string;
	value: number;
	updated_at: string;
	completed_at: string | null;
	heartbeat?: QuestTaskHeartbeat | null;
}

export interface QuestTaskHeartbeat {
	last_beat_at: string;
	expires_at: string | null;
}

export interface QuestApplication {
	id: Snowflake;
	name: string;
	link: string;
}

export interface QuestAssets {
	hero: string;
	hero_video: string | null;
	quest_bar_hero: string;
	quest_bar_hero_video: string | null;
	game_tile: string;
	logotype: string;
}

export interface QuestGradient {
	primary: string;
	secondary: string;
}

export interface QuestMessages {
	quest_name: string;
	game_title: string;
	game_publisher: string;
}

export enum QuestTaskConfigType {
	STREAM_ON_DESKTOP = 'STREAM_ON_DESKTOP',
	PLAY_ON_DESKTOP = 'PLAY_ON_DESKTOP',
	PLAY_ON_DESKTOP_V2 = 'PLAY_ON_DESKTOP_V2',
	PLAY_ON_XBOX = 'PLAY_ON_XBOX',
	PLAY_ON_PLAYSTATION = 'PLAY_ON_PLAYSTATION',
	WATCH_VIDEO = 'WATCH_VIDEO',
	WATCH_VIDEO_ON_MOBILE = 'WATCH_VIDEO_ON_MOBILE',
	PLAY_ACTIVITY = 'PLAY_ACTIVITY',
	ACHIEVEMENT_IN_GAME = 'ACHIEVEMENT_IN_GAME',
	ACHIEVEMENT_IN_ACTIVITY = 'ACHIEVEMENT_IN_ACTIVITY',
}

export interface QuestTaskConfig {
	type: number;
	join_operator: string;
	tasks: Record<QuestTaskConfigType, QuestTask>;
	enrollment_url?: string;
	developer_application_id?: Snowflake;
}

export interface QuestTask {
	event_name: string;
	target: number;
	external_ids?: string[];
	title?: string;
	description?: string;
}

export interface QuestRewardsConfig {
	assignment_method: number;
	rewards: QuestReward[];
	rewards_expire_at: string | null;
	platforms: number[];
}

export interface QuestReward {
	type: number;
	sku_id: Snowflake;
	asset?: string | null;
	asset_video?: string | null;
	messages: QuestRewardMessages;
	approximate_count?: number | null;
	redemption_link?: string | null;
	expires_at?: string | null;
	expires_at_premium?: string | null;
	expiration_mode?: number;
	orb_quantity?: number;
	quantity?: number;
}

export interface QuestRewardMessages {
	name: string;
	name_with_article: string;
	reward_redemption_instructions_by_platform?: Record<number, string>;
}

export interface QuestVideoMetadata {
	messages: QuestVideoMessages;
	assets: QuestVideoAssets;
}

export interface QuestVideoAssets {
	video_player_video_hls: string | null;
	video_player_video: string;
	video_player_thumbnail: string | null;
	video_player_video_low_res: string;
	video_player_caption: string;
	video_player_transcript: string;
	quest_bar_preview_video: string | null;
	quest_bar_preview_thumbnail: string | null;
	quest_home_video: string | null;
}

export interface QuestVideoMessages {
	video_title: string;
	video_end_cta_title: string;
	video_end_cta_subtitle: string;
	video_end_cta_button_label: string;
}

export interface QuestCosponsorMetadata {
	name: string;
	logotype: string;
	redemption_instructions: string;
}

export interface CaptchaDataFromRequest {
	captcha_key: string[];
	captcha_sitekey: string;
	captcha_service: 'hcaptcha';
	captcha_session_id: string;
	captcha_rqdata: string;
	captcha_rqtoken: string;
}
