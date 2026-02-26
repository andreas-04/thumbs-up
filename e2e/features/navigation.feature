Feature: Navigation and Route Protection
  As a user
  I want protected routes to redirect me appropriately
  So that unauthorized access is prevented

  Scenario: Unauthenticated user is redirected from a protected route
    Given I am not logged in
    When I navigate to "/files"
    Then I should be redirected to "/login"

  Scenario: Unauthenticated user is redirected from admin route
    Given I am not logged in
    When I navigate to "/admin/dashboard"
    Then I should be redirected to "/login"

  Scenario: Unknown route shows a 404 page
    Given I am not logged in
    When I navigate to "/this-page-does-not-exist"
    Then I should see "404"

  Scenario: Admin can access the admin dashboard
    Given I am logged in as admin
    When I navigate to "/admin/dashboard"
    Then I should see the admin dashboard
