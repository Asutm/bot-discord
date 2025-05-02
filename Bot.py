import discord
from discord.ext import commands
from discord import app_commands

intents = discord.Intents.default()
intents.guilds = True
intents.messages = True
intents.message_content = False

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

MOD_CHANNEL_ID = 1200129582225961070
PUBLIC_CHANNEL_ID = 1200129454253543456
LOG_CHANNEL_ID = 1362510100060962898  # Remplace ceci par l'ID du canal de logs

pending_confessions = []

BANNED_WORDS = ["sex", "pédo", "nigga", "negger", "nigger", "nega", "fuck", "Shizuku c'est nul"]

def contains_bad_words(text: str):
    return any(word.lower() in text.lower() for word in BANNED_WORDS)

async def send_log(channel, action, user=None, confession_content=None, additional_info=""):
    try:
        log_channel = bot.get_channel(channel)
        if log_channel:
            embed = discord.Embed(
                title=f"🔖 {action} - Log",
                description=(
                    f"**Utilisateur**: {user.mention if user else 'N/A'}\n"
                    f"**Confession**: {confession_content[:100]}..." if confession_content else ""
                ),
                color=discord.Color.green() if "approuvée" in action.lower() else discord.Color.red()
            )
            if additional_info:
                embed.add_field(name="ℹ️ Info supplémentaire", value=additional_info, inline=False)

            await log_channel.send(embed=embed)
        else:
            print(f"[❌] Canal de logs introuvable pour l'ID {channel}")
    except Exception as e:
        print(f"[❌] Erreur lors de l'envoi du log : {e}")
        await log_channel.send(embed=embed)

class VoteView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.upvotes = 0
        self.downvotes = 0

    @discord.ui.button(label="👍 0", style=discord.ButtonStyle.success, custom_id="vote_up")
    async def upvote(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.upvotes += 1
        button.label = f"👍 {self.upvotes}"
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="👎 0", style=discord.ButtonStyle.danger, custom_id="vote_down")
    async def downvote(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.downvotes += 1
        button.label = f"👎 {self.downvotes}"
        await interaction.response.edit_message(view=self)

class ConfessionApprovalView(discord.ui.View):
    def __init__(self, confession_text: str, message_id: int):
        super().__init__(timeout=None)
        self.confession_text = confession_text
        self.message_id = message_id

    @discord.ui.button(label="✅ Approuver", style=discord.ButtonStyle.success)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("⛔ Tu n'as pas la permission de faire ça.", ephemeral=True)
            return

        try:
            public_channel = interaction.guild.get_channel(PUBLIC_CHANNEL_ID)
            if public_channel:
                embed = discord.Embed(
                    title="😶 Nouvelle Confession Anonyme",
                    description=self.confession_text,
                    color=discord.Color.dark_embed()
                )
                embed.set_footer(text="Réagis ou soumets la tienne 👇. N'oublie pas .gg/newshizuku en statut ! 🌙")
                view = SubmitConfessionView(self.confession_text)

                public_message = await public_channel.send(embed=embed, view=view)

                thread = await public_message.create_thread(
                    name="💬 Discussion autour de cette confession",
                    auto_archive_duration=10080
                )

                await thread.send("👇 Que penses-tu de cette confession ?", view=VoteView())

            pending_confessions[:] = [c for c in pending_confessions if c["id"] != self.message_id]
            await interaction.message.delete()
            await send_log(LOG_CHANNEL_ID, "Confession approuvée", interaction.user, self.confession_text)
            await interaction.response.send_message("✅ Confession approuvée et publiée !", ephemeral=True)

        except Exception as e:
            import traceback
            traceback.print_exc()
            await interaction.response.send_message("❌ Une erreur est survenue lors de l'approbation.", ephemeral=True)

    @discord.ui.button(label="❌ Refuser", style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("⛔ Tu n'as pas la permission de faire ça.", ephemeral=True)
            return

        pending_confessions[:] = pending_confessions[:] = [c for c in pending_confessions if c["id"] != self.message_id]

        pending_confessions[:] = [c for c in pending_confessions if c["id"] != self.message_id]
        await interaction.message.delete()

class SubmitConfessionView(discord.ui.View):
    def __init__(self, confession_text: str = "", message_url: str = ""):
        super().__init__(timeout=None)
        self.confession_text = confession_text
        self.message_url = message_url

    @discord.ui.button(label="📝 Soumettre une confession", style=discord.ButtonStyle.primary)
    async def submit(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ConfessionModal())

    @discord.ui.button(label="🚩 Signaler cette confession", style=discord.ButtonStyle.danger)
    async def report(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ReportModal(self.confession_text, self.message_url))

class ConfessionModal(discord.ui.Modal, title="Soumettre une confession anonyme"):
    message = discord.ui.TextInput(
        label="Ta confession",
        placeholder="Écris ta confession ici...",
        style=discord.TextStyle.paragraph,
        max_length=1000
    )

    async def on_submit(self, interaction: discord.Interaction):
        if contains_bad_words(self.message.value):
            await interaction.response.send_message("🚫 Contenu inapproprié détecté. Confession bloquée.", ephemeral=True)
            return

        await interaction.response.send_message("✅ Ta confession a été envoyée aux modérateurs.", ephemeral=True)

        mod_channel = interaction.guild.get_channel(MOD_CHANNEL_ID)
        if mod_channel:
            embed = discord.Embed(
                title="🕵️ Confession à modérer",
                description=self.message.value,
                color=discord.Color.purple()
            )
            embed.set_footer(text="Clique ci-dessous pour valider ou refuser.")
            msg = await mod_channel.send(embed=embed, view=ConfessionApprovalView(self.message.value, interaction.id))

            pending_confessions.append({
                "id": interaction.id,
                "content": self.message.value,
                "message_url": msg.jump_url
            })

class ReportModal(discord.ui.Modal, title="Signaler une confession"):
    def __init__(self, confession_text: str, message_url: str):
        super().__init__()
        self.confession_text = confession_text
        self.message_url = message_url

        self.reason = discord.ui.TextInput(
            label="Raison du signalement",
            placeholder="Ex. : propos haineux, harcèlement...",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=500
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        mod_channel = interaction.guild.get_channel(MOD_CHANNEL_ID)
        if mod_channel:
            embed = discord.Embed(
                title="🚨 Confession signalée",
                description=f"**Confession :**\n{self.confession_text}\n\n**Signalée par :** {interaction.user.mention}",
                color=discord.Color.red()
            )
            embed.add_field(name="Raison du signalement", value=self.reason.value, inline=False)
            if self.message_url:
                embed.add_field(name="🔗 Lien", value=f"[Voir la confession]({self.message_url})", inline=False)

            await mod_channel.send(embed=embed)
        await interaction.response.send_message("✅ Merci ! Le signalement a été transmis à l'équipe Shizuku 🌙.", ephemeral=True)

@tree.command(name="confession", description="Soumettre une confession anonyme.")
async def confession_command(interaction: discord.Interaction):
    await interaction.response.send_modal(ConfessionModal())

@tree.command(name="confessions_en_attente", description="Voir les confessions en attente.")
async def pending(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.manage_messages:
        await interaction.response.send_message("⛔ Tu n'as pas la permission de voir ça.", ephemeral=True)
        return

    if not pending_confessions:
        await interaction.response.send_message("📭 Aucune confession en attente.", ephemeral=True)
        return

    msg = "\n\n".join([f"🔸 `{c['content'][:100]}...`\n🔗 [Voir dans Discord]({c['message_url']})" for c in pending_confessions])
    await interaction.response.send_message(f"🕵️ **Confessions en attente** :\n\n{msg}", ephemeral=True)

@bot.event
async def on_ready():
    await tree.sync()
    activity = discord.Game(name=".gg/newshizuku")
    await bot.change_presence(status=discord.Status.online, activity=activity)
    print(f"✅ Bot connecté en tant que {bot.user.name}")

# Remplace le token ci-dessous par le tien
bot.run("MTM2NzUzOTU5NjM2NzQ5OTQxNQ.Gz762U.bqNvsplPe6imyNdkan8mzTl9jL1Ky5gSpPkQlQ")
