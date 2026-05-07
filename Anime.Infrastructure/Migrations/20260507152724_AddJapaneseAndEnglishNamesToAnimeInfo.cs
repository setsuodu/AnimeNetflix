using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Anime.Infrastructure.Migrations
{
    /// <inheritdoc />
    public partial class AddJapaneseAndEnglishNamesToAnimeInfo : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<string>(
                name: "EnglishTitle",
                table: "Animes",
                type: "character varying(200)",
                maxLength: 200,
                nullable: false,
                defaultValue: "");

            migrationBuilder.AddColumn<string>(
                name: "JapaneseTitle",
                table: "Animes",
                type: "character varying(200)",
                maxLength: 200,
                nullable: false,
                defaultValue: "");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropColumn(
                name: "EnglishTitle",
                table: "Animes");

            migrationBuilder.DropColumn(
                name: "JapaneseTitle",
                table: "Animes");
        }
    }
}
