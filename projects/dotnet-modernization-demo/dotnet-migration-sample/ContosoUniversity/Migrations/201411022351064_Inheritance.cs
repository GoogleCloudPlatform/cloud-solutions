/**
 * Copyright 2025 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License
 */

namespace ContosoUniversity.Migrations
{
    using System;
    using System.Data.Entity.Migrations;
    using System.Diagnostics;

    public partial class Inheritance : DbMigration
    {
        public override void Up()
        {
            // Drop foreign keys and indexes that point to tables we're going to drop.
            Debug.Print("Start");
            DropForeignKey("dbo.Enrollment", "StudentID", "dbo.Student");
            DropIndex("dbo.Enrollment", new[] { "StudentID" });

            RenameTable(name: "dbo.Instructor", newName: "Person");
            AddColumn("dbo.Person", "EnrollmentDate", c => c.DateTime());
            AddColumn("dbo.Person", "Discriminator", c => c.String(nullable: false, maxLength: 128, defaultValue: "Instructor"));
            AlterColumn("dbo.Person", "HireDate", c => c.DateTime());
            AddColumn("dbo.Person", "OldId", c => c.Int(nullable: true));

            // Copy existing Student data into new Person table.
            Sql("INSERT INTO dbo.Person (LastName, FirstName, HireDate, EnrollmentDate, Discriminator, OldId) SELECT LastName, FirstName, null AS HireDate, EnrollmentDate, 'Student' AS Discriminator, ID AS OldId FROM dbo.Student");

            // Fix up existing relationships to match new PK's.
            Sql("UPDATE dbo.Enrollment SET StudentId = (SELECT ID FROM dbo.Person WHERE OldId = Enrollment.StudentId AND Discriminator = 'Student')");

            // Remove temporary key
            DropColumn("dbo.Person", "OldId");

            DropTable("dbo.Student");

            // Re-create foreign keys and indexes pointing to new table.
            AddForeignKey("dbo.Enrollment", "StudentID", "dbo.Person", "ID", cascadeDelete: true);
            CreateIndex("dbo.Enrollment", "StudentID");
            Debug.Print("end");
        }

        public override void Down()
        {
            CreateTable(
                "dbo.Student",
                c => new
                    {
                        ID = c.Int(nullable: false, identity: true),
                        LastName = c.String(nullable: false, maxLength: 50),
                        FirstName = c.String(nullable: false, maxLength: 50),
                        EnrollmentDate = c.DateTime(nullable: false),
                    })
                .PrimaryKey(t => t.ID);

            AlterColumn("dbo.Person", "HireDate", c => c.DateTime(nullable: false));
            DropColumn("dbo.Person", "Discriminator");
            DropColumn("dbo.Person", "EnrollmentDate");
            RenameTable(name: "dbo.Person", newName: "Instructor");
        }
    }
}
