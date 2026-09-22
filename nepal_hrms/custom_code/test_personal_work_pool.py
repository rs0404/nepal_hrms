"""Approved Personal Work may or may not count toward the occurrence pool."""

from unittest import TestCase

import frappe

from nepal_hrms.custom_code.attendance_policy import delay_in_occurrence_pool

GRACE, MAX_DELAY = 15, 60
MINOR, MAJOR, WITHIN_GRACE = 40, 90, 10

OFFICE = frappe._dict(name="A", type_of_work="Office Work")
PERSONAL = frappe._dict(name="A", type_of_work="Personal Work")
UNTYPED = frappe._dict(name="A", type_of_work=None)


def _settings(count_personal):
	return frappe._dict(count_personal_work_in_occurrence_pool=count_personal)


class TestSettingOff(TestCase):
	"""Today's behaviour: an approved slip excuses the occurrence outright."""

	def _pool(self, mins, app):
		return delay_in_occurrence_pool(mins, app, GRACE, MAX_DELAY, _settings(0))

	def test_personal_work_is_excused(self):
		self.assertFalse(self._pool(MINOR, PERSONAL))

	def test_office_work_is_excused(self):
		self.assertFalse(self._pool(MINOR, OFFICE))

	def test_no_application_still_counts(self):
		self.assertTrue(self._pool(MINOR, None))


class TestSettingOn(TestCase):
	"""Personal Work explains the delay but the time was not the company's."""

	def _pool(self, mins, app):
		return delay_in_occurrence_pool(mins, app, GRACE, MAX_DELAY, _settings(1))

	def test_personal_work_now_counts(self):
		self.assertTrue(self._pool(MINOR, PERSONAL))

	def test_office_work_is_still_excused(self):
		self.assertFalse(self._pool(MINOR, OFFICE))

	def test_an_untyped_slip_is_still_excused(self):
		"""Only Personal Work is affected; anything else keeps its excuse."""
		self.assertFalse(self._pool(MINOR, UNTYPED))

	def test_no_application_still_counts(self):
		self.assertTrue(self._pool(MINOR, None))


class TestOnlyMinorsUseThePool(TestCase):
	"""The pool is for minors. A major is charged on the day, whatever the slip."""

	def _pool(self, mins, app, on):
		return delay_in_occurrence_pool(mins, app, GRACE, MAX_DELAY, _settings(on))

	def test_a_major_never_enters_the_pool(self):
		for on in (0, 1):
			for app in (None, OFFICE, PERSONAL):
				self.assertFalse(self._pool(MAJOR, app, on))

	def test_within_grace_never_enters_the_pool(self):
		for on in (0, 1):
			for app in (None, OFFICE, PERSONAL):
				self.assertFalse(self._pool(WITHIN_GRACE, app, on))
