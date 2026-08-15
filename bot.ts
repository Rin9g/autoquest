import { GatewayDispatchEvents, InteractionType, MessageFlags } from 'discord-api-types/v10';
import { ClientQuest } from './src/client';
import { registerCommands } from './src/registerCommands';

let currentUserId: string | null = null;

const botToken = process.env.TOKEN;
if (!botToken) {
	console.error('Error: TOKEN environment variable is missing.');
	process.exit(1);
}

const client = new ClientQuest(botToken);

client.on(GatewayDispatchEvents.InteractionCreate, async ({ data: interaction, api }) => {
	if (interaction.type === InteractionType.ApplicationCommand) {
		const commandData = interaction.data as any;
		if (commandData.name === 'complete-quests') {
			// Instantly defer interaction to prevent "The application did not respond" 3-second timeout
			try {
				await api.interactions.defer(interaction.id, interaction.token, {
					flags: MessageFlags.Ephemeral,
				});
			} catch (deferErr) {
				console.error('Error deferring interaction:', deferErr);
				return;
			}

			const options = commandData.options || [];
			const tokenOption = options.find((opt: any) => opt.name === 'token');
			const userToken: string | undefined = tokenOption?.value;

			if (!userToken || !userToken.trim()) {
				await api.interactions.editReply(interaction.application_id, interaction.token, {
					content: '❌ Please provide a valid Discord user account token.',
				});
				return;
			}

			try {
				await api.interactions.editReply(interaction.application_id, interaction.token, {
					content: '🔒 Scanning account for active quests...',
				});

				const userQuestManager = await client.fetchQuestsForUserToken(userToken.trim(), false);
				const validQuests = userQuestManager.filterQuestsValidToDo();

				if (validQuests.length === 0) {
					await api.interactions.editReply(interaction.application_id, interaction.token, {
						content: '❌ No active, uncompleted quests found on this account.',
					});
					return;
				}

				await api.interactions.editReply(interaction.application_id, interaction.token, {
					content: `🚀 Found ${validQuests.length} valid quest(s). Auto-completing ALL quests now...`,
				});

				const results = await Promise.allSettled(
					validQuests.map((quest) => userQuestManager.doingQuest(quest))
				);

				const succeeded = results.filter((r) => r.status === 'fulfilled').length;

				await api.interactions.followUp(interaction.application_id, interaction.token, {
					content: `🎉 Complete! ${succeeded}/${validQuests.length} quests were finished successfully.`,
					flags: MessageFlags.Ephemeral,
				});

			} catch (err: any) {
				console.error('Error during quest completion:', err);
				await api.interactions.editReply(interaction.application_id, interaction.token, {
					content: `⚠️ Error scanning or completing quests: ${err?.message || err}`,
				});
			}
		}
	}
});

client.once(GatewayDispatchEvents.Ready, async ({ data }) => {
	currentUserId = data.user.id;
	console.log(`Logged in as Bot @${data.user.username} (${data.user.id})`);

	// Auto register commands on startup
	await registerCommands();

	console.log('Bot is ready to accept /complete-quests token:... slash commands.');
});

process.on('unhandledRejection', (reason) => {
	console.error('[Unhandled Rejection]', reason);
});

process.on('uncaughtException', (error) => {
	console.error('[Uncaught Exception]', error.message);
});

client.connect();
