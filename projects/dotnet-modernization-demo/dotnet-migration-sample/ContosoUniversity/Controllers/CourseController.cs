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

using System;
using System.Collections.Generic;
using System.Data;
using System.Data.Entity;
using System.Linq;
using System.Net;
using ContosoUniversity.DAL;
using ContosoUniversity.Models;
using System.Data.Entity.Infrastructure;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.Rendering;
using System.Threading.Tasks;

namespace ContosoUniversity.Controllers
{
    public class CourseController : Controller
    {
        private SchoolContext db = null;

        public CourseController(SchoolContext db)
        {
            this.db = db;
        }

        // GET: Course
        public ActionResult Index(int? SelectedDepartment)
        {
            var departments = db.Departments.OrderBy(q => q.Name).ToList();
            ViewBag.SelectedDepartment = new SelectList(departments, "DepartmentID", "Name", SelectedDepartment);
            int departmentID = SelectedDepartment.GetValueOrDefault();

            IQueryable<Course> courses = db.Courses
                .Where(c => !SelectedDepartment.HasValue || c.DepartmentID == departmentID)
                .OrderBy(d => d.CourseID)
                .Include(d => d.Department);
            var sql = courses.ToString();
            return View(courses.ToList());
        }

        // GET: Course/Details/5
        public ActionResult Details(int? id)
        {
            if (id == null)
            {
                return new BadRequestResult();
            }
            Course course = db.Courses.Find(id);
            if (course == null)
            {
                return new NotFoundResult();
            }
            return View(course);
        }


        public ActionResult Create()
        {
            PopulateDepartmentsDropDownList();
            return View();
        }

        [HttpPost]
        [ValidateAntiForgeryToken]
        public ActionResult Create([Bind("CourseID,Title,Credits,DepartmentID")]Course course)
        {
            try
            {
                if (ModelState.IsValid)
                {
                    db.Courses.Add(course);
                    db.SaveChanges();
                    return RedirectToAction("Index");
                }
            }
            catch (RetryLimitExceededException /* dex */)
            {
                //Log the error (uncomment dex variable name and add a line here to write a log.)
                ModelState.AddModelError("", "Unable to save changes. Try again, and if the problem persists, see your system administrator.");
            }
            PopulateDepartmentsDropDownList(course.DepartmentID);
            return View(course);
        }

        public ActionResult Edit(int? id)
        {
            if (id == null)
            {
                return new BadRequestResult();
            }
            Course course = db.Courses.Find(id);
            if (course == null)
            {
                return new NotFoundResult();
            }
            PopulateDepartmentsDropDownList(course.DepartmentID);
            return View(course);
        }

        [HttpPost, ActionName("Edit")]
        [ValidateAntiForgeryToken]
        public async Task<ActionResult> EditPost(int? id)
        {
            if (id == null)
            {
                return BadRequest();
            }
            var courseToUpdate = db.Courses.Find(id);
            if (await TryUpdateModelAsync(courseToUpdate))
            {
                try
                {
                    db.SaveChanges();

                    return RedirectToAction("Index");
                }
                catch (RetryLimitExceededException /* dex */)
                {
                    //Log the error (uncomment dex variable name and add a line here to write a log.
                    ModelState.AddModelError("", "Unable to save changes. Try again, and if the problem persists, see your system administrator.");
                }
            }
            PopulateDepartmentsDropDownList(courseToUpdate.DepartmentID);
            return View(courseToUpdate);
        }

        private void PopulateDepartmentsDropDownList(object selectedDepartment = null)
        {
            var departmentsQuery = from d in db.Departments
                                   orderby d.Name
                                   select d;
            ViewBag.DepartmentID = new SelectList(departmentsQuery, "DepartmentID", "Name", selectedDepartment);
        }


        // GET: Course/Delete/5
        public ActionResult Delete(int? id)
        {
            if (id == null)
            {
                return new BadRequestResult();
            }
            Course course = db.Courses.Find(id);
            if (course == null)
            {
                return new NotFoundResult();
            }
            return View(course);
        }

        // POST: Course/Delete/5
        [HttpPost, ActionName("Delete")]
        [ValidateAntiForgeryToken]
        public ActionResult DeleteConfirmed(int id)
        {
            Course course = db.Courses.Find(id);
            db.Courses.Remove(course);
            db.SaveChanges();
            return RedirectToAction("Index");
        }

        public ActionResult UpdateCourseCredits()
        {
            return View();
        }

        [HttpPost]
        public ActionResult UpdateCourseCredits(int? multiplier)
        {
            if (multiplier != null)
            {
                ViewBag.RowsAffected = db.Database.ExecuteSqlCommand("UPDATE Course SET Credits = Credits * {0}", multiplier);
            }
            return View();
        }

        protected override void Dispose(bool disposing)
        {
            if (disposing)
            {
                db.Dispose();
            }
            base.Dispose(disposing);
        }
    }
}
