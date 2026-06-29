using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Anime.Infrastructure.Migrations
{
    /// <inheritdoc />
    public partial class AddSiteUpdateTime : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<DateTime>(
                name: "SiteUpdateTime",
                table: "Animes",
                type: "timestamp with time zone",
                nullable: true);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropColumn(
                name: "SiteUpdateTime",
                table: "Animes");
        }
    }
}
