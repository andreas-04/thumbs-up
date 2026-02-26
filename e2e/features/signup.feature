Feature: User Registration
  As a new visitor
  I want to create an account
  So that I can access shared files

  Scenario: Registration fails when passwords do not match
    Given I am on the signup page
    When I fill in "Username" with "anotheruser"
    And I fill in "Email" with "another@thumbsup.local"
    And I fill in "Password" with "Password123!"
    And I fill in "Confirm Password" with "Different456!"
    And I click "Sign Up"
    Then I should see an error message

  Scenario: Registration fails with a short password
    Given I am on the signup page
    When I fill in "Username" with "shortpw"
    And I fill in "Email" with "shortpw@thumbsup.local"
    And I fill in "Password" with "abc"
    And I fill in "Confirm Password" with "abc"
    And I click "Sign Up"
    Then I should see an error message
