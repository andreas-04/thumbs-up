Feature: Authentication
  As a user or admin
  I want to log in and log out
  So that I can securely access the application

  Scenario: Admin logs in with valid credentials
    Given I am on the login page
    When I fill in "Email" with "admin@thumbsup.local"
    And I fill in "Password" with "admin-secret-pw"
    And I click "Sign In"
    Then I should be redirected to "/admin/dashboard"

  Scenario: Regular user logs in with valid credentials
    Given I am on the login page
    When I fill in "Email" with "testuser@thumbsup.local"
    And I fill in "Password" with "user-secret-pw"
    And I click "Sign In"
    Then I should be redirected to "/files"

  Scenario: Login fails with invalid credentials
    Given I am on the login page
    When I fill in "Email" with "nobody@thumbsup.local"
    And I fill in "Password" with "wrong-password"
    And I click "Sign In"
    Then I should see an error message

  Scenario: Admin logs out
    Given I am logged in as admin
    When I log out
    Then I should be redirected to "/login"
