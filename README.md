This project was created in Python with Django framework. It has 4 roles.

1. Customer role is the default role when signing up for an account on the website. The username will be set as the license plate of the first car that you register. Once you are registered, you will be able to add more cars. No license plate can be duplicated in the database. This is why when a user deletes a car, it will be deleted from the system. As the program stands now, if the user deletes the license plate that is the username, the account will be deleted, even if ther eare other cars.

The customer can request service, and when he requests service, he will be able to drag a marker on the map to his address if it does not detect the location. 

2. Concierge

The concierge is who takes the car from customer to dealer and vice versa. The concierge will not be able to see any pending orders to take until the owner (fourth role) clicks that the invoice has been paid. The code is set so the order goes from waiting for payment to pending when the invoice is paid. Then the concierge can put the order in his queue under delivery status. He will be able to see the map on the order. When the order gets put into delivery status, the customer will be able to see the concierge's location.

3. Dealer

The dealer will only see the cars in his queue. This portion of the workflow is being more developed......

4. Owner

His dashboard is the most complex. He can see all invoices, all orders, and he can also add and edit inventory. He can add any other owners, dealers he wants to work with, and concierges he wants to hire. 
