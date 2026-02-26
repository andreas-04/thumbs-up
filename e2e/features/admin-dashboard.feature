Feature: Admin Dashboard
  As an admin
  I want to view system statistics on the dashboard
  So that I can monitor the application

  Background:
    Given I am logged in as admin

  Scenario: Admin sees dashboard stats
    When I navigate to "/admin/dashboard"
    Then I should see the admin dashboard
    And I should see "System Mode"
    And I should see "Approved Users"
    And I should see "Shared Folders"

  Scenario: Admin can navigate to user management
    When I navigate to "/admin/dashboard"
    And I click "Manage Users"
    Then I should be redirected to "/admin/users"

  Scenario: Admin can navigate to file browser
    When I navigate to "/admin/dashboard"
    And I click "File Browser"
    Then I should be redirected to "/admin/files"
